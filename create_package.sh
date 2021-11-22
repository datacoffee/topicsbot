curdir=$(PWD)
docker run --rm -v $curdir:/var/task "python:3.9-slim-buster" /bin/sh -c "cd /var/task;pip3.9 install -r requirements.txt -t python/lib/python3.9/site-packages/; exit"
cd python/lib/python3.9/site-packages
zip -r $curdir/lambda.zip .
cd $curdir
zip -r lambda.zip lambda_function.py
rm -rf python
