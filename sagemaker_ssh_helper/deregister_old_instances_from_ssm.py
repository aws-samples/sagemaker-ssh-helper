from __future__ import annotations

import boto3
ssm = boto3.client('ssm')


def get_ssm_managed_instances():
    print('Getting SSM managed instances using pagination')
    instances = []
    next_token = ""  # nosec hardcoded_password_string  # not a password
    while True:
        response = ssm.describe_instance_information(
            Filters=[{'Key': 'ResourceType', 'Values': ['ManagedInstance']}],
            NextToken=next_token,
            MaxResults=50,
            )
        next_token = response.get('NextToken')
        if response['InstanceInformationList']:
            instances.extend(response['InstanceInformationList'])
            print('Appended {} instances'.format(len(response['InstanceInformationList'])))
        if next_token is None:
            break

    return instances


def filter_instances_regex(instances: list[dict], key, value):
    import re
    len_before = len(instances)
    filtered = []
    for instance in instances:
        if key not in instance:
            print(f"Warning: {key} doesn't exist in {str(instance)}")
            continue
        if re.match(value, instance[key], re.IGNORECASE):
            filtered.append(instance)
    print(f'Filtered out {len_before-len(filtered)} instances missing a regex match for re.match("{value}","{key}")')
    return filtered


def filter_by_tag(instances: list[dict]):
    tagname = 'SSHOwner'
    len_before = len(instances)
    print(f'Will filter through {len_before} instances, verifying they are tagged with "{tagname}".')
    filtered = []
    i = 0
    for instance in instances:
        i += 1
        tags = ssm.list_tags_for_resource(ResourceType='ManagedInstance', ResourceId=instance['InstanceId'])
        if 'TagList' in tags:
            for tag in tags['TagList']:
                if tag['Key'] == tagname:
                    filtered.append(instance)
                    break
        if i % 10 == 0:
            print(f'In progress... Filtered {i} instances for tag name "{tagname}"')
    print(f'Filtered out {len_before-len(filtered)} instances missing the tag "{tagname}"')
    return filtered


def filter_to_ssh_helper_instances(prefilter_instances):
    print('Filtering to SageMaker SSH Helper related instances only')
    filters_def = [
        {'key': 'PingStatus', 'value': 'ConnectionLost'},
    ]
    
    instances = prefilter_instances
    for filter_def in filters_def:
        instances = filter_instances_regex(instances, filter_def['key'], filter_def['value'])

    # TODO: clean up SageMaker Studio instances (can stay down for a while when user switches instances)
    instances = filter_by_tag(instances)

    return instances


def is_approved_to_deregister(instance_count):
    import sys
    if '--preapproving-deregistration' in sys.argv:
        return True
    
    # read interactively
    user_input = input(f'Do you want to deregister these {instance_count} instances? (y/n) ')
    return user_input == 'y'


def deregister(ssh_helper_instances):
    deregistered_success_count = 0
    for instance in ssh_helper_instances:
        instance_id = instance['InstanceId']
        response = ssm.deregister_managed_instance(InstanceId=instance_id)
        if response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(f'{deregistered_success_count}: Deregistered SSM instance {instance_id}')
            deregistered_success_count += 1
        else:
            print(f'Failed to deregister SSM instance {instance_id}. Response: {response}')
            print('Aborting execution.')
            break
    print(f'Successfully deregistered {deregistered_success_count} out of {len(ssh_helper_instances)}'
              f' instances to deregister.')

def main():
    print('This utility will deregister from SSM all SageMaker SSH Helper related managed instances.')
    print('WARNING: you should be careful NOT deregister managed instances that are not related to SageMaker SSH Helper.')
    print('Usage: python deregister_old_instances_from_ssm.py [--preapproving-deregistration]')
    print('--preapproving-deregistration: will automatically approve the deregistration of all instances found, without prompting.')
    print('')
    
    all_managed_instances = get_ssm_managed_instances()
    
    print(f'Found {len(all_managed_instances)} managed instances in total in SSM')
    ssh_helper_instances = filter_to_ssh_helper_instances(all_managed_instances)
    num_of_instances_to_deregister = len(ssh_helper_instances)
    print(f'Found {num_of_instances_to_deregister} managed instances related to SSH Helper')
    
    if is_approved_to_deregister(num_of_instances_to_deregister):
        deregister(ssh_helper_instances)

    print('Done.')


if __name__ == '__main__':
    main()
