pipeline {
  agent any

  stages {
    stage('Setup') {
      steps {
        sh 'python3 --version'
        sh 'python3 -m pip install --upgrade pip'
        sh 'python3 -m pip install -r app/requirements.txt'
        sh 'python3 -m pip install pytest pyyaml'
      }
    }
    stage('Lint') {
      steps {
        sh "python3 -c \"import pathlib,yaml; files=sorted(pathlib.Path('.github/workflows').glob('*.yml')); [yaml.safe_load(open(f, 'r', encoding='utf-8')) for f in files]; print('workflow yaml ok')\""
        sh 'python3 -m compileall app'
      }
    }
    stage('Test') {
      steps {
        sh 'python3 -m pytest app/test_main.py -q'
      }
    }
    stage('Security') {
      steps {
        sh 'python3 -m pip install safety'
        sh 'safety check --file app/requirements.txt || true'
        sh 'python3 -m pip install cyclonedx-bom'
        sh 'cyclonedx-py --output-format json --output-file sbom.json || true'
      }
    }
  }
}
