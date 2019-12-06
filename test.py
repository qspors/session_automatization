import boto3

client = boto3.client('iam')

instance_id = '02027de278d8c0e02'

def search_inline_policy():
    for item in [item for item in
                 [item.get('GroupName') for item in client.list_groups(MaxItems=1000).get('Groups')]
                 if item.split('-')[0].upper() in ['ERS', 'ETL']]:

        try:
            response = client.get_group_policy(GroupName=item, PolicyName='SessionManagerAccess')
            for p_item in response.get('PolicyDocument').get('Statement'):
                if p_item.get('Sid') == 'SessionManager':
                    for r_item in p_item.get('Resource'):
                        if r_item == instance_id:
                            r_item.
                else:
                    pass
        except client.exceptions.NoSuchEntityException:
            pass


search_inline_policy()
