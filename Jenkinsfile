// Jenkins pipeline: the source stages of docs/pipeline-contract.md. The agent has no Docker,
// so image build, signing and release stay in GitHub Actions.
pipeline {
  agent { label 'linux-isolated' }
  options {
    timeout(time: 30, unit: 'MINUTES')
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }
  environment {
    PIP_DISABLE_PIP_VERSION_CHECK = '1'
    PYTHONDONTWRITEBYTECODE = '1'
    // SSH sessions do not inherit the image ENV.
    PATH = "/opt/venv/bin:/usr/local/bin:/usr/bin:/bin"
  }
  stages {
    stage('Source validation') {
      steps {
        deleteDir()
        script {
          if (fileExists('/src/Jenkinsfile')) {
            // Local demonstration: copy the read-only source mount, excluding local tool state.
            sh '''
              set -eu
              tar --exclude=./.venv --exclude=./artifacts --exclude=./zap-out --exclude='*/__pycache__' \
                  --exclude=./infra/jenkins/secrets -C /src -cf - . | tar -xf -
              git config --global --add safe.directory "$PWD"
            '''
          } else {
            checkout scm
          }
        }
        sh 'git log -1 --format="commit %H by %an"'
        // Only commits since the last good build.
        sh '''
          base="${GIT_PREVIOUS_SUCCESSFUL_COMMIT:-$(git rev-parse --verify -q origin/main || git rev-parse HEAD~1)}"
          echo "Checking commits in ${base}..HEAD"
          bash scripts/check-authorship.sh "${base}..HEAD"
        '''
      }
    }
    stage('Lint') {
      steps {
        sh 'python -m ruff check . --no-cache'
        sh 'python -m ruff format --check . --no-cache'
        sh 'python -m mypy app scripts/oidc scripts/release update-signing/bastion_update firmware-sim/boot_sim.py --cache-dir=/tmp/mypy'
        sh 'python -m yamllint --strict .'
      }
    }
    stage('Unit tests and coverage gate') {
      steps {
        sh 'python -m pytest -p no:cacheprovider --cov --cov-report=term --cov-report=xml:coverage.xml --cov-fail-under=85 --junitxml=junit.xml'
      }
      post {
        always { junit 'junit.xml' }
      }
    }
    stage('Secret scan') {
      steps {
        sh 'gitleaks dir . --redact --no-banner --exit-code 1'
      }
    }
    stage('Dependency analysis') {
      steps {
        sh 'osv-scanner scan source --config osv-scanner.toml -L app/requirements.txt -L app/requirements-dev.txt -L update-signing/requirements.txt'
      }
    }
  }
  post {
    always {
      archiveArtifacts artifacts: 'coverage.xml,junit.xml', allowEmptyArchive: true
    }
  }
}
