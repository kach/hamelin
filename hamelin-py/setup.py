from setuptools import setup, find_packages

setup(name = 'hamelin',
      version = '0.0.1',
      author = 'hardmath123',
      url = 'https://github.com/hardmath123/hamelin',
      description = 'some reference implementations of the hamelin spec',
      license = 'MIT',
      packages = find_packages(),
      install_requires = [],
      entry_points = {
        'console_scripts': ['hamelin-net = hamelin.net:main']
      },
      classifiers = [
        "Programming Language :: Python",
      ],
)
