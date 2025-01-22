from setuptools import setup, find_packages

setup(
    name="twix",  # Replace with your library name
    version="0.1.0",  # Initial version
    author="Yiming Lin",
    author_email="yiminglin@berkeley.edu",
    description="A library that extracts structured data from templatized form-like documents automatically.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yiminl18/document_reverse.git",  # Repository URL
    packages=find_packages(),  # Automatically find packages in your project
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",  # Minimum Python version
    install_requires=[
        "pytesseract",
        "pdfplumber",
        "pandas",
        "numpy",
        "scipy",
        "tiktoken",
        "pdf2image",
        "gurobipy",
        "openai"
    ],
)
