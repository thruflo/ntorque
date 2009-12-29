from setuptools import setup, find_packages

setup(
    name = 'torque',
    version = '0.4.1',
    description = 'A web hook task queue based on tornado and redis',
    long_description = open('README.rst').read(),
    author = 'James Arthur',
    author_email = 'thruflo@googlemail.com',
    url = 'http://github.com/thruflo/torque',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: Public Domain',
        'Programming Language :: Python'
    ],
    license = 'Creative Commons CC0 1.0 Universal',
    packages = find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data = True,
    zip_safe = False,
    install_requires=[
        'setuptools_git==0.3.4',
        'pycurl==7.18.1',
        'simplejson==2.0.9',
        'tornado==0.2',
        'redis==0.6.1',
        'nose==0.11.1'
    ],
    test_suite = 'nose.collector',
    entry_points = {
        'setuptools.file_finders': [
            'findfiles = setuptools_git:gitlsfiles'
        ],
        'console_scripts': [
            'torque-serve = torque.webapp:main',
            'torque-process = torque.processor:main'
        ]
    }
)