from setuptools import setup, find_packages

setup(
    name = 'ntorque',
    version = '0.3.3',
    description = 'Web hook task queue service.',
    author = 'James Arthur',
    author_email = 'username: thruflo, domain: gmail.com',
    url = 'http://ntorque.com',
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: Public Domain',
        'Programming Language :: Python :: 2.7',
    ],
    license = 'http://unlicense.org',
    packages = find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data = True,
    zip_safe = True,
    entry_points = {
        'setuptools.file_finders': [
            'ls = setuptools_git:gitlsfiles'
        ],
        'console_scripts': [
            'ntorque_cleanup = ntorque.work.cleanup:main',
            'ntorque_consume = ntorque.work.consume:main',
            'ntorque_requeue = ntorque.work.requeue:main'
        ]
    }
)
