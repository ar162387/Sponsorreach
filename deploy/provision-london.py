"""Provision only SponsorReach's isolated London pilot. Never touches existing hosts."""
import base64
import json
import subprocess
from pathlib import Path
import uuid

REGION = 'eu-west-2'
NAME = 'sponsorreach-london'
ROLE = NAME + '-ssm'
PROFILE = NAME + '-profile'


def aws(service, operation, **args):
    command = ['aws', service, operation, '--region', REGION, '--no-cli-pager', '--output', 'json']
    for name, value in args.items():
        command += ['--' + name.replace('_', '-'), json.dumps(value) if isinstance(value, (dict, list)) else str(value)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main():
    existing = aws('ec2', 'describe-instances', filters=[{'Name': 'tag:Project', 'Values': ['SponsorReach']}])
    live = [i for r in existing['Reservations'] for i in r['Instances'] if i['State']['Name'] not in {'terminated', 'shutting-down'}]
    if live:
        print(json.dumps({'existing_instances': [{'id': i['InstanceId'], 'state': i['State']['Name']} for i in live]}))
        return
    image = aws('ssm', 'get-parameter', name='/aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp3/ami-id')['Parameter']['Value']
    detail = aws('ec2', 'describe-images', image_ids=[image])['Images'][0]
    assert detail['OwnerId'] == '099720109477' and detail['Architecture'] == 'arm64'
    subnets = aws('ec2', 'describe-subnets', filters=[{'Name': 'default-for-az', 'Values': ['true']}])['Subnets']
    subnet = sorted([s for s in subnets if s['MapPublicIpOnLaunch']], key=lambda s: s['AvailabilityZone'])[0]
    groups = aws('ec2', 'describe-security-groups', filters=[{'Name': 'group-name', 'Values': [NAME + '-web']}])['SecurityGroups']
    group = groups[0]['GroupId'] if groups else aws('ec2', 'create-security-group', group_name=NAME + '-web', description='SponsorReach isolated web; administration through SSM only', vpc_id=subnet['VpcId'])['GroupId']
    # Leave ingress closed until the application passes its private checks.
    try:
        aws('iam', 'get-role', role_name=ROLE)
    except RuntimeError as error:
        if 'NoSuchEntity' not in str(error): raise
        aws('iam', 'create-role', role_name=ROLE, assume_role_policy_document={'Version': '2012-10-17', 'Statement': [{'Effect': 'Allow', 'Principal': {'Service': 'ec2.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]})
    aws('iam', 'attach-role-policy', role_name=ROLE, policy_arn='arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore')
    try:
        profile = aws('iam', 'get-instance-profile', instance_profile_name=PROFILE)['InstanceProfile']
    except RuntimeError as error:
        if 'NoSuchEntity' not in str(error): raise
        profile = aws('iam', 'create-instance-profile', instance_profile_name=PROFILE)['InstanceProfile']
    if not profile.get('Roles'):
        aws('iam', 'add-role-to-instance-profile', instance_profile_name=PROFILE, role_name=ROLE)
    bootstrap = '''#!/bin/bash
set -eu
install -d -m 0755 /opt/sponsorreach /etc/sponsorreach
if ! id sponsorreach >/dev/null 2>&1; then useradd --system --home /opt/sponsorreach --shell /usr/sbin/nologin sponsorreach; fi
chown sponsorreach:sponsorreach /opt/sponsorreach
if ! test -f /swapfile; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
install -d /etc/systemd/journald.conf.d
printf '[Journal]\\nSystemMaxUse=100M\\n' > /etc/systemd/journald.conf.d/sponsorreach.conf
systemctl restart systemd-journald
'''
    tags = [{'Key': 'Name', 'Value': NAME}, {'Key': 'Project', 'Value': 'SponsorReach'}, {'Key': 'OperatorManaged', 'Value': 'manual-csv'}, {'Key': 'BudgetReviewDate', 'Value': '2026-12-31'}]
    data = {
        'ImageId': image, 'InstanceType': 't4g.small',
        'IamInstanceProfile': {'Name': PROFILE},
        'MetadataOptions': {'HttpTokens': 'required', 'HttpEndpoint': 'enabled', 'HttpPutResponseHopLimit': 1},
        'CreditSpecification': {'CpuCredits': 'standard'},
        'Monitoring': {'Enabled': False},
        'NetworkInterfaces': [{'DeviceIndex': 0, 'AssociatePublicIpAddress': True, 'DeleteOnTermination': True, 'SubnetId': subnet['SubnetId'], 'Groups': [group]}],
        'BlockDeviceMappings': [{'DeviceName': detail['RootDeviceName'], 'Ebs': {'VolumeSize': 20, 'VolumeType': 'gp3', 'Encrypted': True, 'DeleteOnTermination': True}}],
        'UserData': base64.b64encode(bootstrap.encode()).decode(),
        'TagSpecifications': [{'ResourceType': kind, 'Tags': tags} for kind in ['instance', 'volume']],
    }
    templates = aws('ec2', 'describe-launch-templates', filters=[{'Name': 'launch-template-name', 'Values': [NAME]}])['LaunchTemplates']
    if templates:
        template = templates[0]['LaunchTemplateId']
        version = aws('ec2', 'create-launch-template-version', launch_template_id=template, launch_template_data=data)['LaunchTemplateVersion']['VersionNumber']
    else:
        template = aws('ec2', 'create-launch-template', launch_template_name=NAME, launch_template_data=data)['LaunchTemplate']['LaunchTemplateId']
        version = 1
    # Persist the token before launching. Reconcile an ambiguous timeout instead of blindly retrying.
    state = {'region': REGION, 'template': template, 'version': version, 'group': group, 'client_token': str(uuid.uuid4()), 'status': 'launch_pending'}
    path = Path(__file__).with_name('london-instance.json')
    path.write_text(json.dumps(state, indent=2))
    launched = aws('ec2', 'run-instances', launch_template={'LaunchTemplateId': template, 'Version': str(version)}, count=1, client_token=state['client_token'])['Instances'][0]
    state.update(instance_id=launched['InstanceId'], status=launched['State']['Name'])
    path.write_text(json.dumps(state, indent=2))
    print(json.dumps(state))


if __name__ == '__main__':
    main()
