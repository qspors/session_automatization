import boto3
import json
from boto3.exceptions import Boto3Error


def lambda_handler(event, context):
    template = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "SessionManager",
                "Effect": "Allow",
                "Action": [
                    "ssm:StartSession"
                ],
                "Resource": [
                    "arn:aws:ec2:*:*:instance/i-00000000000000000"
                ]
            },
            {
                "Sid": "SetOfRights",
                "Effect": "Allow",
                "Action": [
                    "ssm:DescribeSessions",
                    "ssm:GetConnectionStatus",
                    "ssm:DescribeInstanceProperties",
                    "ec2:DescribeInstances"
                ],
                "Resource": "*"
            },
            {
                "Sid": "GetDocument",
                "Effect": "Allow",
                "Action": [
                    "ssm:GetDocument"
                ],
                "Resource": [
                    "arn:aws:ssm:*:*:document/SSM-SessionManagerRunShell4"
                ],
                "Condition": {
                    "BoolIfExists": {
                        "ssm:SessionDocumentAccessCheck": "true"
                    }
                }
            },
            {
                "Sid": "TerminateSession",
                "Effect": "Allow",
                "Action": [
                    "ssm:TerminateSession"
                ],
                "Resource": [
                    "arn:aws:ssm:*:*:session/*"
                ]
            }
        ]
    }
    while True:
        state = check_instance_state(event=event)
        if state is True:
            return False
        instance_type = check_instance_type(event=event)
        if instance_type is False:
            return instance_type
        instance_id, app, stage, team, state = get_info(event=event)
        if state is False:
            return state
        if list_policy_from_bucket(stage=stage, team=team):
            json_data, state = get_file_from_bucket(stage=stage, team=team)
        else:
            file_name, state = create_policy_file(stage=stage, team=team, json_data=template)
            if state is False:
                return state
            json_data, state = get_file_from_bucket(stage=stage, team=team)
            if state is False:
                return state
        json_data, state = update_policy(instance_id=instance_id, json_data=json_data)
        if state is False:
            return state
        update_group(team=team, stage=stage, json_data=json_data)
        create_policy_file(stage=stage, team=team, json_data=json_data)
        return {
            'statusCode': 200,
            'body': json.dumps(event)
        }


def check_instance_type(event: dict) -> bool:
    print('check instance Type')
    try:
        tag_set = [item['key'] for item in [tags for tags in
                                            event['detail']['responseElements']['instancesSet'][
                                                'items'][
                                                0]['tagSet']['items']]]

        if 'App' not in tag_set:
            return False
        else:
            return True
    except KeyError:
        return False


def check_instance_state(event: dict):
    print('Check instance State')
    instance_id = []
    for item in event.get('detail').get('responseElements').get('instancesSet').get('items'):
        instance_id.append(item.get('instanceId'))
    for idx, i_item in enumerate(instance_id):
        state = event.get('detail').get("eventName")
        if state == 'TerminateInstances':
            clean_policy(instance_id=i_item)
        elif state == 'RunInstances':
            continue
        else:
            return True
    return False


def list_policy_from_bucket(stage: str, team: str) -> bool:
    client = boto3.client('s3')
    policy_name_file = 'policy-{}-{}.json'.format(stage, team)
    bucket_name = 'sessionmb'
    objects_list = []
    try:
        objects_response = client.list_objects_v2(
            Bucket=bucket_name,
            MaxKeys=10000,

        ).get('Contents')
        if objects_response is None:
            return False
        for item in objects_response:
            objects_list.append(item.get('Key'))
        if policy_name_file in objects_list:
            return True
        else:
            return False
    except (ValueError, Boto3Error) as e:
        return False


def get_info(event: dict) -> tuple:
    print('get_info Group')
    instance_id = []
    stage = ''
    app = ''
    team = ''
    try:
        for item in event.get('detail').get('responseElements').get('instancesSet').get('items'):
            instance_id.append(item.get('instanceId'))
            for tag_item in item.get('tagSet').get('items'):
                if tag_item.get('key') == 'App':
                    app = tag_item.get('value')
                elif tag_item.get('key') == 'Stage':
                    stage = tag_item.get('value')
                elif tag_item.get('key') == 'Team':
                    team = tag_item.get('value')
        return instance_id, app, stage, team, True
    except ValueError as e:
        return None, None, None, None, False


def update_group(stage: str, team: str, json_data: dict) -> bool:
    print('Update Group')
    client = boto3.client('iam')
    try:
        json_doc = json.dumps(json_data)
        group_name = '{}-{}'.format(team, stage).upper()
        policy_name = 'SessionManagerAccess'
        client.put_group_policy(
            GroupName=group_name,
            PolicyName=policy_name,
            PolicyDocument=json_doc
        )
        return True
    except Boto3Error:
        return False


def update_policy(instance_id: list, json_data: dict) -> tuple:
    print('Update policy')
    temp_list = []
    try:
        for i_item in json_data.get('Statement'):
            if i_item.get('Sid') == 'SessionManager':
                for z_item in i_item.get('Resource'):
                    temp_list.append(z_item.split('/')[1])
    except ValueError:
        return None, False
    for instance_id_item in instance_id:
        try:
            if instance_id_item in temp_list:
                continue
            for item in json_data.get('Statement'):
                if item.get('Sid') == 'SessionManager':
                    item.get('Resource').append('arn:aws:ec2:*:*:instance/{}'.format(instance_id_item))
        except ValueError:
            return None, False
    return json_data, True


def get_file_from_bucket(stage: str, team: str):
    print('Get file from bucket')
    s3 = boto3.resource('s3')
    bucket_name = 'sessionmb'
    file_name = 'policy-{}-{}.json'.format(stage, team)
    try:
        obj = s3.Object(bucket_name, file_name)
        body = obj.get()['Body'].read()
        json_data = json.loads(body)
        return json_data, True
    except Boto3Error as e:
        return None, False


def create_policy_file(stage: str, team: str, json_data: dict):
    print('Create policy file')
    client = boto3.client('s3')
    bucket_name = 'sessionmb'
    file_name = 'policy-{}-{}.json'.format(stage, team)
    try:
        json_doc = json.dumps(json_data).encode('utf-8')
        client.put_object(Bucket=bucket_name, Body=json_doc, Key=file_name)
        return file_name, True
    except Boto3Error:
        return None, False


def clean_policy(instance_id: str):
    client = boto3.client('s3')
    s3 = boto3.resource('s3')
    bucket_name = 'sessionmb'
    objects_list = []
    try:
        objects_response = client.list_objects_v2(
            Bucket=bucket_name,
            MaxKeys=10000,
        ).get('Contents')
        if objects_response is None:
            print('Trigger is activated')
            return False
        for item in objects_response:
            objects_list.append(item.get('Key'))
        for file_object in objects_list:
            obj = s3.Object(bucket_name, file_object)
            body = obj.get()['Body'].read()
            json_data = json.loads(body)
            for item in json_data.get('Statement'):
                if item.get('Sid') == 'SessionManager':
                    for r_item in item.get('Resource'):
                        if r_item.split('/')[1] == instance_id:
                            item.get('Resource').remove('arn:aws:ec2:*:*:instance/{}'.format(instance_id))
                            stage = file_object.split('-')[1]
                            team = file_object.split('-')[2]
                            team = team.split('.')[0]
                            create_policy_file(stage=stage, team=team, json_data=json_data)
                            update_group(stage=stage, team=team, json_data=json_data)
                            return True
    except Boto3Error:
        return False
