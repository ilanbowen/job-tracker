IMAGE_NAME ?= job-tracker-app:local
NAMESPACE ?= job-tracker
RELEASE ?= job-tracker

.PHONY: dev build import-k3s deploy status port-forward logs uninstall

dev:
	./scripts/dev-local.sh

build:
	docker build -t $(IMAGE_NAME) .

import-k3s: build
	docker save $(IMAGE_NAME) | sudo k3s ctr images import -

deploy:
	helm upgrade --install $(RELEASE) ./helm/job-tracker --namespace $(NAMESPACE) --create-namespace

status:
	kubectl get all,pvc,ingress -n $(NAMESPACE)

port-forward:
	kubectl port-forward -n $(NAMESPACE) svc/$(RELEASE)-app 8000:80

logs:
	kubectl logs -n $(NAMESPACE) deploy/$(RELEASE)-app -f

uninstall:
	helm uninstall $(RELEASE) -n $(NAMESPACE)
