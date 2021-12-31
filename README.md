# seatable-syncer

## Docker build

* cd syncer/frontend
* npm install --no-audit
* npm run build
* vim Dockerfile, SYNC_VERSION=x.x.x
* docker build -t seatable/seatable-syncer-test:x.x.x ./
