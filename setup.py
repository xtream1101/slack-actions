from distutils.core import setup

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst', format='md')
except (IOError, ImportError) as e:
    print(str(e))
    long_description = ''

setup(
    name='slack-actions',
    packages=['slack_actions'],
    version='0.1.0',
    description='Build custom slackbots with ease',
    long_description=long_description,
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
