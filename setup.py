import setuptools


with open("README.md") as a:
    long_description = a.read()


with open("requirements.txt") as a:
    requirements = a.read().splitlines()


setuptools.setup(
    name="Streamlink",
    version="0.0.1",
    author="Kae Bartlett",
    author_email="kae@voxelfox.co.uk",
    description="",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    packages=[
        "streamlink",
        "streamlink.cogs",
        "streamlink.cogs.utils",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',
    install_requires=requirements,
)
