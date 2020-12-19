# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import requests
import commands
import json
import ldap
import re
import gitlab
import sys

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, HttpResponse
reload(sys) 
sys.setdefaultencoding('utf8') 


# gitlab webhook
def host_port(project_name):
    host_port_dict = {
        'test1-service': '30001',
        'test2-service': '30002',
    }

    return host_port_dict[project_name]


def gitlab_namespace(namespace):
    '''
    gitlab namespace对应分组
    '''
    group_dict = {
        # 用于测试钉钉机器人token
        'backend': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        'frontend': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    }

    return group_dict[namespace]


def get_token(access_token):
    '''
    钉钉管理后台 : http://open-dev.dingtalk.com
    '''
    # 这个是test的机器人token
    url_token = 'https://oapi.dingtalk.com/robot/send?access_token=%s' % access_token

    return url_token


def send_dingding(url_token, content, at_people):
    '''
    url_token: 网站
    content: 发送的内容
    at_people: 要at的人
    '''
    msgtype = 'text'
    if at_people == '':
        values = {
            'msgtype': 'text',
            msgtype: {
                'content': content
            },
            'at': {
                'atMobiles': ['18888888888','+86-18888888888'],
            },
        }
    else:
        values = {
            'msgtype': 'text',
            msgtype: {
                'content': content
            },
            'at': {
                'atMobiles': [at_people]
            },
        }

    headers = {'Content-Type': 'application/json; charset=UTF-8'}
    values = json.dumps(values)
    res = requests.post(url_token, values, headers=headers)
    errmsg = json.loads(res.text)['errmsg']

    if errmsg == 'ok':
        return 'ok'

    return 'fail: %s' % res.text


def ldap_login():
    '''
    login ldap
    '''
    con = ldap.initialize('ldap://vickey-wu.com:30003')
    con.simple_bind_s("cn=admin,dc=vickey-wu,dc=com", "mypassword")

    return con


def get_phone(search_key, search_value):
    '''
    获取ldap用户手机号用于在钉钉通知消息中@人
    search_key为mail, cn, sn这3个ldap返回信息的key，不能随意更改
    '''
    con = ldap_login()
    ldap_base = "dc=vickey-wu,dc=com"
    query = "(" + search_key +"=" + search_value + ")"
    print('search_key:%s, search_value:%s' % (search_key, search_value))
    result = con.search_s(ldap_base, ldap.SCOPE_SUBTREE, query)
    #print('ldap result: ', result)
    try:
        at_people = result[0][1]['mobile']
        print('search_key:%s, search_value:%s, at_people:%s' % (search_key, search_value, at_people))
    except Exception as e:
        at_people = ''
        print('ldap error:', e, search_value)
    return at_people


def gitlab_issue(request_body):
    '''
    process gitlab webhook issue
    '''
    webhook_info = request_body
    project = webhook_info['project']['web_url']
    namespace = webhook_info['project']['path_with_namespace'].split("/")[0]
    url = webhook_info['object_attributes']['url']
    state = webhook_info['object_attributes']['state']
    title = webhook_info['object_attributes']['title']
    description = webhook_info['object_attributes']['description'][:200] + '\n' + '更多详情查看问题链接' + url
    user = webhook_info['user']['name']
    username = webhook_info['user']['username']
    labels_list = []
    labels_length = len(webhook_info['labels'])
    assignee_name = ''
    assignee_username = ''

    for l in range(labels_length):
        labels_list.append(str(webhook_info['labels'][l]['title']))
    if labels_list == []:
        labels = 'no setted label'
    else:
        labels = ', '.join(labels_list)
    try:
        assignee_name = webhook_info['assignees'][0]['name']
        assignee_username = webhook_info['assignees'][0]['username']
    except Exception as e:
        print("issue Error:", e)
        assignee_name = "未分配"
    content = '项目: %s\n问题链接: %s\n问题状态: %s\n问题标题: %s\n问题标签： %s\n问题描述: %s\n问题创建者: %s\n问题分配给: %s' % \
              (project, url, state, title, labels, description, user, assignee_name)
    print(content)

    if state == 'opened':
        at_people = ''
        if username != assignee_username and assignee_username != '':
            print(type(assignee_username))
            at_people = get_phone('sn', assignee_username)
            if at_people == '':
                at_people = get_phone('cn', assignee_name)
                #at_people = get_phone('sn', assignee_username)
        send_dingding(get_token(gitlab_namespace(namespace)), content, at_people)
        pass


def get_version(project_id, job_id):
    ############### 调用python-gitlab的trace函数获取job版本信息 ################
    ## 用python-gitlab的关于job的trace函数输出job打印的信息, token为admin账号的token，失效重新生成即可
    gl = gitlab.Gitlab('https://git.vickey-wu.com', private_token='d1b-GrJj1wkscz2Exya2')
    project_by_id = gl.projects.get(project_id)
    job = project_by_id.jobs.get(job_id)
    info = job.trace()

    ## .gitlab-ci.yml中会将镜像版本信息打上tag，所以我们可以从build阶段的job输出日志获取提镜像版本信息
    tag_start_word = "Successfully tagged "
    version = None
    tag = re.search(tag_start_word + '(\S+)', info).group(1)
    print("tag info: ", tag)

    if '_' in tag:
        tmp_tag = tag.split(':')[1].split('_')
        list_len = len(tmp_tag)
        if list_len > 2:
            version = tmp_tag[0]
            deploy_time = tmp_tag[1]
            print('tag with version', version, deploy_time)
        else:
            version = version
            deploy_time = tmp_tag[0]
            print('tag no version', version, deploy_time)
    else:
        tmp_tag = tag.split(':')[1].split('-')
        tag_len = len(tmp_tag)
        if tag_len == 3:
            version = tmp_tag[0] + '-' +  tmp_tag[1]
            deploy_time = tmp_tag[2]
            print('tag with sha v1', version, deploy_time)
        else:
            version = tmp_tag[0]
            deploy_time = tmp_tag[1]
            print('tag with sha v2', version, deploy_time)

    print("get_version info:", version, deploy_time)
    return ([version, deploy_time])


def gitlab_pipeline(request_body):
    '''
     proccess gitlab webhook pipeline
    '''
    # 现有gitlab-ci只有build和deploy两个阶段，一般最后一个阶段是deploy
    webhook_info = request_body
    project = webhook_info['project']['web_url']
    project_name = webhook_info['project']['name']
    project_id = webhook_info['project']['id']
    branch = webhook_info['object_attributes']['ref']
    namespace = webhook_info['project']['path_with_namespace'].split("/")[0]
    search_value = webhook_info['commit']['author']['email']
    user = webhook_info['builds'][-1]['user']['name']
    message = webhook_info['commit']['message']

    # 添加项目ip端口信息
    project_info = '项目信息缺失'
    project_name = webhook_info['project']['name']
    print(project_name)
    at_people = ''
    version = None
    deploy_time = '暂无时间信息'
    version_list = [version, deploy_time]

    try:
        port_info = host_port(project_name)
        # ip为k8s公网ip
        project_info = 'test.vickey-wu.com:' + port_info
    except Exception as er:
        print('project_info', er)

    # 获取build阶段的个数，找到对应的build阶段的id及状态
    build_dict = {}
    deploy_dict = {}
    all_stage = len(webhook_info['builds'])
    job_id_build_tmp = 0
    job_id_deploy_tmp = 0

    for bn in range(all_stage):
        build_name = webhook_info['builds'][bn]['name']
        job_id = webhook_info['builds'][bn]['id']
        build_status = webhook_info['builds'][bn]['status']
        #print('build info', build_name, job_id, build_status)

        # 找到最大的job_id即为最新运行产生的job，如果还有build03... 那就再加一个判断，一般不会超过2个吧。。
        if (build_name == 'build' and job_id > job_id_build_tmp) or (build_name == 'build02' and job_id > job_id_build_tmp):
            # 过滤掉手动执行的job
            #if build_status != 'manual':
            if build_status != 'manual':
                build_dict[build_name] = [job_id, build_status]
                job_id_build_tmp = job_id
        print('build dictory', build_dict)
        # 同理可得deploy阶段最新job_id
        if (build_name == 'deploy' and job_id > job_id_deploy_tmp) or (build_name == 'deploy02' and job_id > job_id_deploy_tmp) or \
        (build_name == 'deploy-prod' and job_id > job_id_deploy_tmp) or (build_name == 'deploy-prod-app' and job_id > job_id_deploy_tmp) or\
        (build_name == 'deploy-prod-admin' and job_id > job_id_deploy_tmp):
            # 过滤掉手动执行的job,build_status等同于deploy_status
            if build_status != 'manual':
                deploy_dict[build_name] = [job_id, build_status]
                job_id_deploy_tmp = job_id
        # 防止deploy测试和deploy-prod生产两个部署的时候重复发钉钉通知
        if len(deploy_dict) >= 2:
            if deploy_dict['deploy-prod'][0] > deploy_dict['deploy'][0]:
                del deploy_dict['deploy']
            else:
                del deploy_dict['deploy-prod']
         
    print('build stage', build_dict)
    print('deploy stage', deploy_dict)

    for build_name in build_dict:
        # 如果build阶段失败就发通知
        build_status = build_dict[build_name][1]
        print(build_status)
        job_id = build_dict[build_name][0]
        if build_status == 'failed':
            deploy_status = "build失败了，老铁..."
            content = '部署者: %s\n最后提交: %s\n部署项目: %s\n部署地址：%s\n部署所属分支: %s\n部署状态: %s\n' % \
                      (user, message, project, project_info, branch, deploy_status)
            at_people = get_phone('mail', search_value)
            send_dingding(get_token(gitlab_namespace(namespace)), content, at_people)
        # 在build阶段获取版本信息，在deploy阶段使用
        elif build_status == 'success':
            print(project_id, job_id)
            version_list = get_version(project_id, job_id)
            print(version_list)

    #print("version_list:", version_list)

    # 如果build阶段成功，则进入deploy阶段，不管deploy成功还是失败均发通知
    for deploy_name in deploy_dict:
        deploy_status = deploy_dict[deploy_name][1]
        if deploy_status == 'failed':
            deploy_status = "deploy失败了，老铁..."
            content = '部署者: %s\n最后提交: %s\n部署项目: %s\n部署地址：%s\n部署所属分支: %s\n部署状态: %s\n' % \
                      (user, message, project, project_info, branch, deploy_status)
            at_people = get_phone('mail', search_value)
            if deploy_name == 'deploy-prod' or deploy_name == 'deploy-prod-app' or deploy_name == 'deploy-prod-admin':
                namespace = namespace + '-prod'
                print('namespace-prod: ', namespace)
                content = '部署者: %s\n最后提交: %s\n部署项目: %s\n部署所属分支: %s\n部署状态: %s\n' % \
                      (user, message, project, branch, deploy_status)
            send_dingding(get_token(gitlab_namespace(namespace)), content, at_people)
        elif deploy_status == 'success':
            # 处理版本信息
            try:
                version, deploy_time = version_list[0], version_list[1]
                #print("vvvvvvvvv", version, deploy_time)
            except Exception as e:
                print(e)

            if version != None:
                content = '部署者: %s\n最后提交: %s\n部署项目: %s\n部署地址：%s\n部署所属分支: %s\n部署镜像版本: %s\n部署状态: %s\n镜像提交时间或SHA值: %s' % \
                          (user, message, project, project_info, branch, version, deploy_status, deploy_time)
            else:
                content = '部署者: %s\n最后提交: %s\n部署项目: %s\n部署地址：%s\n部署所属分支: %s\n部署状态: %s\n镜像提交时间或SHA值: %s' % \
                          (user, message, project, project_info, branch, deploy_status, deploy_time)
            print(content)
            if deploy_name == 'deploy-prod' or deploy_name == 'deploy-prod-app' or deploy_name == 'deploy-prod-admin':
                namespace = namespace + '-prod'
                if version != None:
                    content = '部署者: %s\n最后提交: %s\n部署项目: %s\n部署所属分支: %s\n部署镜像版本: %s\n部署状态: %s\n镜像提交时间或SHA值: %s' % \
                              (user, message, project, branch, version, deploy_status, deploy_time)
                else:
                    content = '部署者: %s\n最后提交: %s\n部署项目: %s\n部署所属分支: %s\n部署状态: %s\n镜像提交时间或SHA值: %s' % \
                              (user, message, project, branch, deploy_status, deploy_time)
                print("生产信息:", content)
            send_dingding(get_token(gitlab_namespace(namespace)), content, at_people)
        else:
            pass


def gitlab_merge_request(request_body):
    '''
    process gitlab webhook merge_request
    '''
    webhook_info = request_body
    project = webhook_info['project']['web_url']
    namespace = webhook_info['project']['path_with_namespace'].split("/")[0]
    url = webhook_info['object_attributes']['url']
    state = webhook_info['object_attributes']['state']
    title = webhook_info['object_attributes']['title']
    description = webhook_info['object_attributes']['description'][:200] + '\n' + '更多详情查看合并链接' + url
    email = webhook_info['object_attributes']['last_commit']['author']['email']
    user = webhook_info['user']['name']
    username = webhook_info['user']['username']
    assignee_name = ''
    assignee_username = ''

    # 如果未分配该key:assignee不存在，做个异常处理
    try:
        assignee_name = webhook_info['assignees'][0]['name']
        assignee_username = webhook_info['assignees'][0]['username']
    except Exception as err:
        print("merge Error", err)
        assignee_name = "未分配"
    
    content = '合并项目: %s\n合并链接: %s\n合并状态: %s\n标题: %s\n合并请求描述: %s\n合并发起者: %s\n请求分配给: %s' % \
              (project, url, state, title, description, user, assignee_name)
    print(content)

    if state == 'opened':
        # 如果分配给自己不会@自己，号码为空也不会@人
        at_people = ''
        if username != assignee_username and assignee_username != '':
            #print('not equal', type(assignee_name), len(assignee), assignee_name, at_people)
            at_people = get_phone('sn', assignee_username)
            if at_people == '':
                at_people = get_phone('cn', assignee_name)
        send_dingding(get_token(gitlab_namespace(namespace)), content, at_people)


@csrf_exempt
def gitlab_webhook(request):
    '''
    proccess gitlab webhook request
    '''
    if request.method == 'POST':
        print(request.body)
        request_body = json.loads(request.body)
        webhook_kind = request_body['object_kind']

        if webhook_kind == 'issue':
            gitlab_issue(request_body)
        if webhook_kind == 'pipeline':
            gitlab_pipeline(request_body)
        if webhook_kind == 'merge_request':
            gitlab_merge_request(request_body)
        else:
            pass
        return HttpResponse('Done!')


# jira webhook
def jira_token(namespace):
    group_dict = {
        # 用于测试钉钉机器人token
        'test1': 'xxxxxxxxxxxxxxxxxxxxxx',
        'test2': 'xxxxxxxxxxxxxxxxxxxxxx',
    }

    return group_dict[namespace]


def jira_create(request_body):
    print('the same as jira_update')


def jira_update(request_body):
    webhook_info = request_body
    at_people = ''
    bill_project = webhook_info['issue']['fields']['project']['key']
    print(bill_project)
    bill_id = webhook_info['issue']['key']
    bill_url = 'https://jira.vickey-wu.com/browse/' + bill_id
    bill_creator = webhook_info['issue']['fields']['creator']['displayName']
    bill_status = webhook_info['issue']['fields']['status']['name']
    if bill_status == '发布':
       bill_status = '完成'
    bill_title = webhook_info['issue']['fields']['summary']
    #print(type(bill_description), bill_description)
    bill_description = ''
    description = webhook_info['issue']['fields']['description']
    if description != None:
        bill_description = webhook_info['issue']['fields']['description'][:200] + '\n' + '更多详情查看问题链接' + bill_url
    bill_assignee = '未分配'
    bill_assignee_dis = '未分配'
    try:
        bill_assignee = webhook_info['issue']['fields']['assignee']['name']
        bill_assignee_dis = webhook_info['issue']['fields']['assignee']['displayName']
    except Exception as e:
        print('assignee error', e)
    if bill_creator != bill_assignee:
        at_people = get_phone('sn', bill_assignee)

    content = '工单标题：%s\n工单概要：%s\n创建者: %s\n分配给: %s\n工单链接: %s\n工单状态: %s' % \
              (bill_title, bill_description, bill_creator, bill_assignee_dis, bill_url, bill_status)
    print(content)
    if bill_project == 'TEST1':
        send_dingding(get_token(jira_token(bill_project)), content, at_people)


@csrf_exempt
def jira(request):
    if request.method == 'POST':
        print(request.body)
        request_body = json.loads(request.body)
        webhook_kind = request_body['webhookEvent']
        if webhook_kind == 'jira:issue_created':
            jira_update(request_body)
        if webhook_kind == 'jira:issue_updated':
            jira_update(request_body)
        return HttpResponse('Done!')
    else:
        return HttpResponse('unsupport')
