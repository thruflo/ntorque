pip install -U pip
pip install -U setuptools
pip install setuptools_git

pip install -r requirements.txt --allow-all-external --exists-action i --timeout 30
pip install -e .
