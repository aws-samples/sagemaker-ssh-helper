from __future__ import annotations

import logging
import sys

import boto3

from sagemaker_ssh_helper.manager import SSMManager

logging.basicConfig(level=logging.INFO)


def is_approved_to_deregister(instance_count):
    if '--preapproving-deregistration' in sys.argv:
        return True

    # read interactively
    user_input = input(f'Do you want to deregister these {instance_count} instances? (y/n) ')
    return user_input == 'y'


def deregister(ssh_helper_instances):
    ssm = boto3.client('ssm')
    deregistered_success_count = 0
    for instance_id in ssh_helper_instances:
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
    print('Usage: python deregister_old_instances_from_ssm.py [--preapproving-deregistration] [--delete-older-than-n-days <N>]')
    print('--preapproving-deregistration: will automatically approve the deregistration of all instances found, without prompting.')
    print('--delete-older-than-n-days <N>: will only delete offline instances that are older than N days.')
    print('')

    try:
        index = sys.argv.index('--delete-older-than-n-days')
        days = int(sys.argv[index + 1])
    except ValueError or IndexError:
        days = 0

    manager = SSMManager()
    ssh_helper_instances = manager.list_expired_ssh_instances(days)

    num_of_instances_to_deregister = len(ssh_helper_instances)

    if is_approved_to_deregister(num_of_instances_to_deregister):
        deregister(ssh_helper_instances)

    print('Done.')


if __name__ == '__main__':
    main()
