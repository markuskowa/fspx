import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name = "fspx",
    version = "0.1",
    author = "Markus Kowalewski",
    author_email = "markus.kowalewski@gmail.com",
    description = "Functional Scientific Project Execution",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url = "https://github.com/markuskowa/fspx",
    packages = setuptools.find_packages(),
     entry_points={
        'console_scripts': ['fspx=fspx.fspx:main']
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPL 3.0 only",
        "Operating System :: OS Independent",
    ],     python_requires='>=3.8'
)


