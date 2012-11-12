%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           python-ordereddict
Version:        1.1
Release:        5%{?dist}
Summary:        Implementation of Python 2.7's OrderedDict
Group:          Development/Languages
License:        MIT
URL:            http://pypi.python.org/pypi/ordereddict
Source0:        http://pypi.python.org/packages/source/o/ordereddict/ordereddict-1.1.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:      noarch
BuildRequires:  python-devel

%description
Drop-in substitute for Py2.7's new collections.OrderedDict. 
Originally based on http://code.activestate.com/recipes/576693/

%prep
%setup -q -n ordereddict-%{version}

%build
%{__python} setup.py build

%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc LICENSE
%{python_sitelib}/*

%changelog
* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.1-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Sat Jan 14 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.1-4
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Tue Feb 08 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.1-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Thu Oct 28 2010 James Ni <jni@redhat.com> 1.1-2
- Modify the spec file and update to upstream source

* Wed Jul 14 2010 James Ni <jni@redhat.com> 1.1-1
- Initial RPM release

