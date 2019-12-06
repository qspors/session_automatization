import boto3
import json
import os
from boto3.exceptions import Boto3Error


def lambda_handler(event, context):
    if UserManagement().get_users_tags():
        return {
            'statusCode': 200,
            'body': json.dumps('Secret update Successfully')
        }
    else:
        return {
            'statusCode': 503,
            'body': json.dumps('Secret update Failed')
        }


class UserManagement:
    def __init__(self):
        self.iam = boto3.client('iam')
        self.secret = boto3.client('secretsmanager')
        self.secret_id = os.environ.get('ARN')

    def list_users(self) -> list:
        client = self.iam
        response = client.list_users(
            MaxItems=1000
        )
        return [item.get('UserName') for item in response.get('Users')]

    def get_users_tags(self) -> bool:
        user_list_for_access = []
        user_list = self.list_users()
        client = self.iam
        for item in user_list:
            response = client.get_user(
                UserName=item
            )
            try:
                tags = response.get('User')['Tags']
                user_name = response.get('User').get('UserName')
                sudo = ''
                for tag_item in tags:
                    if tag_item['Key'].lower() == 'session' and tag_item['Value'].lower() == 'true':
                        for s_item in tags:
                            if s_item.get('Key') == 'sudo'.lower():
                                sudo = s_item.get('Value').lower()
                        user_list_for_access.append({user_name: sudo})
            except KeyError:
                pass
        if self.update_secrets(user_list=user_list_for_access):
            return True
        else:
            return False

    def update_secrets(self, user_list: list) -> bool:
        try:
            self.secret.update_secret(
                SecretId=self.secret_id,
                SecretString='{}'.format(user_list)
            )
            return True
        except Boto3Error:
            return False

