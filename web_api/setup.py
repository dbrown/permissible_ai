"""
Setup configuration for the Permissible TEE Web API
"""
from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

with open('requirements.txt', 'r', encoding='utf-8') as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='permissible-tee-api',
    version='0.1.0',
    author='Your Name',
    author_email='your.email@example.com',
    description='Trusted Execution Environment API using Google Cloud Platform',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/permissible',
    packages=find_packages(exclude=['tests', 'tests.*', 'docs', 'scripts']),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Security',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Framework :: Flask',
    ],
    python_requires='>=3.8',
    install_requires=requirements,
    extras_require={
        'dev': [
            'pytest>=7.4.0',
            'pytest-cov>=4.1.0',
            'pytest-flask>=1.2.0',
            'black>=23.7.0',
            'flake8>=6.1.0',
            'mypy>=1.5.0',
            'isort>=5.12.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'permissible-api=wsgi:application',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
