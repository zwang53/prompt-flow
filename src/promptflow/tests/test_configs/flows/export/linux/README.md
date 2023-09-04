Exported Dockerfile & its dependencies are located in the same folder. The structure is as below:
- flow: the folder contains all the flow files
  - ...
- connections: the folder contains yaml files to create all related connections
  - ...
- Dockerfile: the dockerfile to build the image
- start.sh: the script used in `CMD` of `Dockerfile` to start the service
- deploy.sh & deploy.ps1: the script to deploy the docker image to Azure App Service
- settings.json: a json file to store the settings of the docker image
- README.md: the readme file to describe how to use the dockerfile

Please refer to [official doc](https://microsoft.github.io/promptflow/how-to-guides/deploy-and-export-a-flow.html#export-a-flow)
for more details about how to use the exported dockerfile and scripts.
