import json
import boto3
import calendar
import os
from datetime import datetime, date, time,timedelta

SNS_TOPIC = os.environ['SNS_TOPIC']

def get_current_month_first_day_zero_time():
    today = date.today()
    first_day = today.replace(day=1)
    first_day_zero_time = datetime.combine(first_day, time.min)
    return first_day_zero_time
    
def get_current_month_last_day_last_time():
    today = date.today()
    last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    last_day_last_time = datetime.combine(last_day, time(23, 59, 59))
    return last_day_last_time
    
def stop_instance(instance_name):
    client = boto3.client('lightsail')
    response = client.stop_instance(
        instanceName=instance_name,
        force=True
    )
    
def list_instances(instances_list):
    client = boto3.client('lightsail')
    paginator = client.get_paginator('get_instances')
    # Create a PageIterator from the Paginator
    page_iterator = paginator.paginate()
    for page in page_iterator:
        for instance in page['instances']:
            print(instance['name'])
            instances_list.append(instance['name'])
        
        

def get_month_dto_quota(instance_name):
    client = boto3.client('lightsail')
    response = client.get_instance(
        instanceName=instance_name
    )
    #print("response : {}".format(response))
    dto_quota = response['instance']['networking']['monthlyTransfer']['gbPerMonthAllocated']
    current_datetime = datetime.now()
    instance_created_datetime = response['instance']['createdAt']
    if (instance_created_datetime.year == current_datetime.year) and (instance_created_datetime.month == current_datetime.month):
        month_ts = get_current_month_last_day_last_time().timestamp() - get_current_month_first_day_zero_time().timestamp()
        instance_valide_ts = get_current_month_last_day_last_time().timestamp() - instance_created_datetime.timestamp()
        dto_quota = (instance_valide_ts/month_ts) * dto_quota
        print("created in current month, quota: {}GB".format(dto_quota))
    else:
        dto_quota = response['instance']['networking']['monthlyTransfer']['gbPerMonthAllocated']
        print("created in previous month, full quota: {}GB".format(dto_quota))
    
    return dto_quota
    
def get_instance_data_usage(instance_name, data_type):
    
    client = boto3.client('lightsail')
    
    # 获取当前时间
    current_time = datetime.utcnow()
   
    
    # 计算开始时间（当前时间减去24小时）
    start_time = get_current_month_first_day_zero_time()
    end_time = get_current_month_last_day_last_time()

    # 将时间转换为ISO 8601格式字符串
    start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
    end_time_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')

    response = client.get_instance_metric_data(
        instanceName=instance_name,
        metricName=data_type,
        period= 6 * 600 * 24,  # 指定获取数据的时间间隔，这里设置为1天
        unit='Bytes',
        statistics=[
            'Sum'
        ],
        startTime=start_time_str,
        endTime=end_time_str 
    )

    data_points = response['metricData']
    total_data_usage = sum([data_point['sum'] for data_point in data_points])
    print("total {} usage: {}".format(data_type, total_data_usage))
    return total_data_usage

def push_notification(arn, msg):
    sns_client = boto3.client('sns')
    # Publish a message to a topic
    print("sqs arn: {}".format(arn))
    response = sns_client.publish(
        TopicArn=arn,
        Message=msg,
        Subject='Lightsail NetworkOut exceeded quota '
    )

def lambda_handler(event, context):
    instance_name= []
    list_instances(instance_name)
    for i in instance_name:
        quota = get_month_dto_quota(i) * 1000 * 1000 * 1000
        total = get_instance_data_usage(i, "NetworkOut") + get_instance_data_usage(i, "NetworkIn") 
        msg = f"instance_name: {i} \nusage: {total} Byte \nquota: {quota} Byte \nusage percent: {(total/quota)*100} %"
        print(msg)
        
        if int(quota) < int(total):
            print("quota < total, soforce close instance: {}".format(1))
            push_notification(SNS_TOPIC, msg)
            stop_instance(i)
             
    return {
        'statusCode': 200,
        'body': json.dumps('total_data_usage from Lambda!')
    }
