pip install -U pip
pip install -U setuptools==0.8
pip install setuptools_git==1.1
pip install -r requirements.txt --allow-all-external --exists-action i --timeout 30
pip install -e .
