FROM vickeywu/django-python2

EXPOSE 8000

RUN apt-get update -y

RUN apt-get install apt-utils -y \
 && apt-get install python-dev -y \
 && apt-get install libldap2-dev -y \
 && apt-get install libsasl2-dev -y \
 && apt-get install libevent-dev -y \
 && apt-get install build-essential -y \
 && apt-get install curl -y \
 && apt-get install vim -y

RUN apt-get install python-pip -y \
 && pip install requests \
 && pip install --upgrade python-gitlab \
 && python -m pip install python-ldap

WORKDIR /webhook

CMD python manage.py runserver 0.0.0.0:8000
