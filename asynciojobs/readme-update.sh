#!/bin/bash
jupyter nbconvert --ExecutePreprocessor.timeout=600 --to notebook --execute README.ipynb
mv -f README.nbconvert.ipynb README.ipynb
