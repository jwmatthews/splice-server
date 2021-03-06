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

from django.http import HttpResponse

from splice.common.auth import X509CertificateAuthentication

# Unit test imports
from base import BaseEntitlementTestCase


class X509CertificateAuthenticationTest(BaseEntitlementTestCase):

    def setUp(self):
        super(X509CertificateAuthenticationTest, self).setUp()
        self.x509_auth = X509CertificateAuthentication(verification_ca=self.splice_server_identity_ca_pem)
    def tearDown(self):
        super(X509CertificateAuthenticationTest, self).tearDown()

    def test_with_no_certificate(self):
        req = self.request_factory.request()
        CN, O = self.x509_auth.get_identifier(req)
        self.assertIsNone(CN)
        self.assertIsNone(O)
        resp = self.x509_auth.is_authenticated(request=req)
        self.assertIsInstance(resp, HttpResponse)
        self.assertHttpUnauthorized(resp)

    def test_with_valid_certificate(self):
        req = self.request_factory.request(SSL_CLIENT_CERT=self.valid_identity_cert_pem)
        CN, O = self.x509_auth.get_identifier(req)
        self.assertEqual(CN, self.expected_valid_splice_server_identity_uuid)
        self.assertEqual(O, self.expected_valid_splice_server_identity_num)
        self.assertTrue(self.x509_auth.is_authenticated(request=req))

    def test_with_invalid_certificate(self):
        req = self.request_factory.request(SSL_CLIENT_CERT=self.invalid_identity_cert_pem)
        resp = self.x509_auth.is_authenticated(request=req)
        self.assertIsInstance(resp, HttpResponse)
        self.assertHttpUnauthorized(resp)