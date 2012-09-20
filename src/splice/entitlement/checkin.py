# -*- coding: utf-8 -*-
#
# Copyright © 2012 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.


import logging
import time
import pytz

from datetime import datetime, timedelta
from uuid import UUID

from splice.common import candlepin_client, utils
from splice.common.certs import CertUtils
from splice.common.config import CONFIG, get_candlepin_config_info, get_splice_server_info
from splice.common.exceptions import CheckinException, CertValidationException, UnallowedProductException, \
    UnknownConsumerIdentity
from splice.common.identity import sync_from_rhic_serve
from splice.entitlement.models import ConsumerIdentity, ProductUsage, SpliceServer

_LOG = logging.getLogger(__name__)

SPLICE_SERVER_INFO = get_splice_server_info()

class CheckIn(object):
    """
    Logic for recording a consumers usage and returning an entitlement certificate
    will be implemented here.
    """
    def __init__(self):
        self.cert_utils = CertUtils()
        f = None
        try:
            self.root_ca_path = CONFIG.get("security", "root_ca_cert")
            f = open(self.root_ca_path, "r")
            self.root_ca_cert_pem = f.read()
        finally:
            if f:
                f.close()

    def get_this_server(self):
        # parse a configuration file and determine our splice server identifier
        # TODO  read in a SSL cert that identifies our splice server.
        server_uuid = SPLICE_SERVER_INFO["uuid"]
        hostname = SPLICE_SERVER_INFO["hostname"]
        environment = SPLICE_SERVER_INFO["environment"]
        description = SPLICE_SERVER_INFO["description"]
        server = SpliceServer.objects(uuid=server_uuid).first()
        if not server:
            server = SpliceServer(
                uuid=server_uuid,
                description=description,
                hostname=hostname,
                environment=environment
            )
            try:
                server.save()
            except Exception, e:
                _LOG.exception(e)
        return server

    def get_entitlement_certificate(self, identity_cert, consumer_identifier,
                                    facts, installed_products, cert_length_in_min=None):
        """
        @param identity_cert: str containing X509 certificate, identify of the consumer
        @type identity_cert: str

        @param consumer_identifier: a str to help uniquely identify consumers in a given network, could be MAC address
        @type consumer_identifier: str

        @param facts info about the hardware from the consumer, memory, cpu, etc
        @type facts: {}

        @param installed_products: a list of X509 certificates, identifying each product installed on the consumer
        @type products: [str]

        @return:    a list of tuples, first entry is a string of the x509 certificate in PEM format,
                    second entry is the associated private key in string format
        @rtype: [(str,str)]
        """
        if not self.validate_cert(identity_cert):
            raise CertValidationException()

        identity = self.get_identity(identity_cert)

        allowed_products, unallowed_products = self.check_access(identity, installed_products)
        if unallowed_products:
            raise UnallowedProductException(identity, unallowed_products)

        cert_info = self.request_entitlement(identity, allowed_products, cert_length_in_min)
        # TODO:  Must add system facts to reporting data
        self.record_usage(identity, consumer_identifier, facts, allowed_products)
        return cert_info

    def validate_cert(self, cert_pem):
        """
        @param cert_pem: x509 encoded pem certificate as a string
        @param cert_pem: str

        @return: true if 'cert_pem' was signed by the configured root CA, false otherwise
        @rtype: bool
        """
        _LOG.info("Validate the identity_certificate is signed by the expected CA from '%s'" % (self.root_ca_path))
        _LOG.debug(cert_pem)
        return self.cert_utils.validate_certificate_pem(cert_pem, self.root_ca_cert_pem)

    def extract_id_from_identity_cert(self, identity_cert):
        subj_pieces = self.cert_utils.get_subject_pieces(identity_cert)
        if subj_pieces and subj_pieces.has_key("CN"):
            return subj_pieces["CN"]
        return None

    def get_identity(self, identity_cert):
        id_from_cert = self.extract_id_from_identity_cert(identity_cert)
        _LOG.info("Found ID from identity certificate is '%s' " % (id_from_cert))
        identity = ConsumerIdentity.objects(uuid=UUID(id_from_cert)).first()
        if not identity:
            _LOG.info("Couldn't find RHIC with ID '%s' initiating a sync from RHIC_Serve" % (id_from_cert))
            sync_from_rhic_serve()
            raise UnknownConsumerIdentity(id_from_cert)
        return identity

    def check_access(self, identity, installed_products):
        """
        @param identity the consumers identity
        @type identity: splice.common.models.ConsumerIdentity

        @param installed_products list of product ids representing the installed engineering products
        @type installed_products: [str, str]]

        @return tuple of list of allowed products and list of unallowed products
        @rtype [],[]
        """
        _LOG.info("Check if consumer identity <%s> is allowed to access products: %s" % \
                  (identity, installed_products))
        allowed_products = []
        unallowed_products = []
        for prod in installed_products:
            if prod not in identity.engineering_ids:
                unallowed_products.append(prod)
            else:
                allowed_products.append(prod)
        return allowed_products, unallowed_products

    def record_usage(self, identity, consumer_identifier, facts, products):
        """
        @param identity consumer's identity
        @type identity: str

        @param consumer_identifier means of uniquely identifying different instances with same consumer identity
            an example could be a mac address
        @type consumer_identifier: str

        @param facts system facts
        @type facts: {}

        @param products: list of product ids
        @type products: [entitlement.models.Product]
        """
        try:
            sanitized_facts = utils.sanitize_dict_for_mongo(facts)
            _LOG.info("Record usage for '%s' with products '%s' on instance with identifier '%s' and facts <%s>" %\
                (identity, products, consumer_identifier, sanitized_facts))
            consumer_uuid_str = str(identity.uuid)
            prod_usage = ProductUsage(consumer=consumer_uuid_str, splice_server=self.get_this_server(),
                instance_identifier=consumer_identifier, product_info=products, facts=sanitized_facts,
                date=datetime.now())
            prod_usage.save()
        except Exception, e:
            _LOG.exception(e)
        return

    def request_entitlement(self, identity, allowed_products, cert_length_in_min=None):
        cp_config = get_candlepin_config_info()
        installed_products=allowed_products
        start_date=None
        end_date=None
        if cert_length_in_min:
            start_date = datetime.now(tz=pytz.utc)
            end_date = start_date + timedelta(minutes=cert_length_in_min)
            start_date = start_date.isoformat()
            end_date = end_date.isoformat()

        _LOG.info("Request entitlement certificate from external service: %s:%s%s for RHIC <%s> with products <%s>" %\
                    (cp_config["host"], cp_config["port"], cp_config["url"], identity.uuid, installed_products))

        cert_info = candlepin_client.get_entitlement(
            host=cp_config["host"], port=cp_config["port"], url=cp_config["url"],
            installed_products=installed_products,
            identity=str(identity.uuid),
            username=cp_config["username"], password=cp_config["password"],
            start_date=start_date, end_date=end_date)
        return cert_info

