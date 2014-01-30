from setuptools import setup, find_packages

setup(
    name = 'torque',
    version = '2.0',
    description = 'Web hook task queue service.',
    long_description = open('README.md').read(),
    author = 'James Arthur',
    author_email = 'username: thruflo, domain: gmail.com',
    url = 'http://documentup.com/thruflo/torque',
    classifiers = [
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: Public Domain',
        'Programming Language :: Python'
    ],
    license = open('UNLICENSE').read(),
    packages = find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data = True,
    zip_safe = True,
    entry_points = {
        'setuptools.file_finders': [
            'ls = setuptools_git:gitlsfiles'
        ],
        'console_scripts': [
            'torque_consume = torque.work.consume:main',
            'torque_requeue = torque.work.requeue:main'
        ]
    }
)
