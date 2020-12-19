#### build
```
docker build -f ./Dockerfile -t webhook:v1  ./
```
#### run docker container
```
docker run -itd --name gitlab_webhook -v /home/webhook:/webhook -p 8000:8000 webhook:v1
```
