// Tests, then deploys to this same box and restarts the app.
// The app listens on 127.0.0.1:$PORT; a Cloudflare Tunnel ingress
// ($PUBLIC_HOST -> http://localhost:$PORT) provides the public HTTPS address.
//
// Needs two "Secret text" credentials in Jenkins:
//   live-translator-openai-key   the OpenAI API key
//   live-translator-password     the password asked for when opening the page
pipeline {
  agent any

  environment {
    DEPLOY_DIR = '/opt/live-translator'
    PUBLIC_HOST = 'translate.sherifs.de'
    PORT = '6303'
  }

  options {
    timestamps()
    disableConcurrentBuilds()
    timeout(time: 10, unit: 'MINUTES')
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Test') {
      steps { sh 'python3 test_server.py' }
    }

    stage('Deploy') {
      steps {
        withCredentials([
          string(credentialsId: 'live-translator-openai-key', variable: 'OPENAI_API_KEY'),
          string(credentialsId: 'live-translator-password', variable: 'APP_PASSWORD')
        ]) {
          sh '''
            mkdir -p "$DEPLOY_DIR" 2>/dev/null || {
              sudo -n mkdir -p "$DEPLOY_DIR"
              sudo -n chown "$(id -un)" "$DEPLOY_DIR"
            }

            # Never touch the saved calls or the runtime files on the server.
            rsync -a --delete \
              --exclude='.git' --exclude='__pycache__' \
              --exclude='calls.db' --exclude='app.pid' --exclude='app.log' \
              ./ "$DEPLOY_DIR/"

            cd "$DEPLOY_DIR"
            if [ -f app.pid ] && ps -p "$(cat app.pid)" -o args= 2>/dev/null | grep -q server.py; then
              kill "$(cat app.pid)"
              sleep 1
            fi

            # The secrets reach the app through its environment only; nothing is written to disk.
            # JENKINS_NODE_COOKIE stops Jenkins from killing the app when the build ends.
            # Not restarted after a reboot: run this job again.
            JENKINS_NODE_COOKIE=dontKillMe nohup python3 -u server.py >> app.log 2>&1 &
            echo $! > app.pid
          '''
        }
      }
    }

    stage('Smoke test') {
      steps {
        sh '''
          # 401 means the app is up and asking for the password.
          for i in $(seq 1 20); do
            code=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $PUBLIC_HOST" "http://127.0.0.1:$PORT/" || true)
            if [ "$code" = 401 ]; then echo "app is up"; exit 0; fi
            sleep 1
          done
          echo "app did not come up"; tail -20 "$DEPLOY_DIR/app.log"; exit 1
        '''
      }
    }
  }

  post {
    success { echo "Deployed build #${env.BUILD_NUMBER} to https://${env.PUBLIC_HOST}" }
  }
}
