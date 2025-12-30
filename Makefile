include .env
export

IMAGE_TAG := $(GCP_REGION)-docker.pkg.dev/$(GCP_PROJECT)/$(GCP_ARTIFACT_REPO)/app:latest

.PHONY: deploy build push run

deploy: build push run

build:
	docker build --platform linux/amd64 -t $(IMAGE_TAG) .

push:
	docker push $(IMAGE_TAG)

run:
	gcloud run deploy $(GCP_SERVICE_NAME) --image $(IMAGE_TAG) --region $(GCP_REGION)
