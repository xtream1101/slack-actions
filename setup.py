from setuptools import setup

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name='slack-actions',
    packages=['slack_actions'],
    version='0.3.1',
    description='Build custom slackbots with ease',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Eddy Hintze',
    author_email="eddy@hintze.co",
    url="https://github.com/xtream1101/slack-actions",
    license='MIT',
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    install_requires=['slackclient',
                      'falcon',
                      'gunicorn',
                      ],
)
