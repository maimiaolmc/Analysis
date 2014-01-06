#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
@author: zhoujiebin
@contact: zhoujiebing@maimiaotech.com
@date: 2013-05-24 11:12
@version: 1.0.0
@license: Copyright maimiaotech.com
@copyright: Copyright maimiaotech.com

"""
if __name__ == '__main__':
    import sys
    sys.path.append('../../')
import os
import datetime
from DataAnalysis.conf.settings import logger, CURRENT_DIR
from CommonTools.send_tools import send_email_with_file, DIRECTOR
from CommonTools.report_tools import Report, MAIN_KEYS 
from user_center.services.order_db_service import OrderDBService
from DataAnalysis.db_model.shop_db import Shop
import csv
import re

def write_renew_report(file_name, nick_list):
    """收集nick_list的报表"""
    
    print_keys = ['nick', 'campaign', 'multi_cost', 'multi_cpc', 'multi_roi', \
            'multi_cvr', 'multi_ctr', 'count_days']
    header_keys = ['店铺昵称', '计划名称', '多天花费', '多天cpc', '多天roi', '多天转化率',\
            '多天点击率', '统计天数']
    write_obj = file(CURRENT_DIR+'data/renew_report.csv', 'w')
    write_obj.write(','.join(header_keys)+'\n')

    for line in file(file_name):
        campaign = Report.parser_report(line)
        if not campaign:
            continue

        if campaign['nick'] in nick_list:
            report_str = []
            for key in print_keys:
                if key in ['multi_cost', 'multi_cpc']:
                    campaign[key] /= 100.0
                elif key in ['multi_cvr', 'multi_ctr', 'multi_roi']:
                    campaign[key] = '%.3f' % campaign[key]
                report_str.append(str(campaign[key]))
            #TODO 增加联系方式 以及 电话营销人员id
            write_obj.write(','.join(report_str)+'\n')
    
    write_obj.close()

def collect_renew_nicks(start_time, end_time, article_code_list=['ts-1796606', 'ts-1797607', 'ts-1817244']):
    """收集所有某时间段内过期但未续费的用户"""

    user_orders = {}
    article_nicks = {}
    for article_code in article_code_list:
        article_nicks[article_code] = []

    all_order = OrderDBService.get_all_orders_list()
    for order in all_order:
        if order['article_code'] not in article_code_list:
            continue
        key = (order['nick'], order['article_code'])
        if not user_orders.has_key(key):
            user_orders[key] = []
        user_orders[key].append(order)
        
    for key in user_orders.keys():
        orders = user_orders[key]
        orders.sort(key=lambda order:order['order_cycle_start'])
        
        for i in range(len(orders)):
            order = orders[i]
            deadline = order['order_cycle_end']
            if deadline >= start_time and deadline <= end_time:
                if i == len(orders) - 1:
                    article_nicks[order['article_code']].append(order['nick'])
                    break
            elif deadline > end_time:
                break
    
    return article_nicks

def auto_support_script():
    try:
        auto_support_service()
    except Exception,e:
        logger.exception('auto_support_script error: %s', str(e))
        send_sms(DIRECTOR['PHONE'], 'auto_support_script error: %s' % (str(e)))
    else:
        logger.info('auto_support_script ok')

def special_content_service():
    """将淘宝给我们的建议放入到自动留言里"""

    #加载留言模版
    content_list = ['下标从1开始']
    content = ''
    for line in file(CURRENT_DIR+'data/content_template.csv'):
        if line == '\r\n':
            content_list.append(content)
            content = ''
        content += line
    
    #加载留言用户
    nicks_list = file(CURRENT_DIR+'data/content_nick.csv').read().split('\n')
    for line in nicks_list:
        line_data = line.split(',')
        if len(line_data) >= 2:
            id = int(line_data[0])
            content = content_list[id]
            for nick in line_data[1:]:
                if not nick:
                    break
                message_dict = {'status':'new', 'worker':'', 'message':content}
                print  nick,message_dict["message"]
                #if Shop.upsert_cs_message(nick, message_dict):
                #    print nick + ":" + str(id)
        
def special_content_service_new():
    """
    将淘宝给我们的建议放入到自动留言里
    现在是用户名和建议放在同一个文件中,    
    第一行为标题，第二行开始为实际内容 ,格式: nic ,留言内容,(等其他信息)
    """

    
    #加载留言用户
    liuyan = file(CURRENT_DIR+'data/liuyan0809.csv')
    liuyan_list=csv.reader(liuyan)
    index=0
    for line_data in liuyan_list:
        index+=1
        if index==1:
            continue
        if len(line_data)>=2:
            nick=line_data[0]
            message=line_data[3]
            message=message.replace("#",",")
            r=re.compile("\n{2,}")
            message=r.sub("\n",message)
            #print "%s,%s" % (index,message)
            if nick is None or nick=="":
                print nick,message
                continue
            message_dict={"status":"new","worker":"","message":message}
            if Shop.upsert_cs_message(nick, message_dict):
                print "%s\t%s" %(nick,index)



def auto_support_service():
    """自动生成特殊服务支持"""
    MESSAGE_A = '亲爱的掌柜您好~谨代表麦苗团队全体成员欢迎您入驻省油宝！不知亲这两天使用下来感觉怎么样呢？有问题要随时和我联系哦，如果我不在线，亲可以留言呢~！期待与亲有更多的交流，一定竭诚为亲服务的！'
    MESSAGE_B = '亲,您的软件还有3天就要到期了. 如果亲觉得效果不错,请及时续费!到期后省油宝将会把托管的所有词价格重置为0.05元！'
    user_info = {}
    all_order = OrderDBService.get_all_orders_list()
    for order in all_order:
        if order['article_code'] != 'ts-1796606':
            continue
        key = order['nick']
        pre_order = user_info.get(key, None)
        if not pre_order:
            user_info[key] = order 
        else:
            if order['order_cycle_start'] < pre_order['order_cycle_start']:
                pre_order['order_cycle_start'] = order['order_cycle_start']
            if order['order_cycle_end'] > pre_order['order_cycle_end']:
                pre_order['order_cycle_end'] = order['order_cycle_end']
   
    today = datetime.date.today()
    for nick in user_info: 
        order = user_info[nick]
        message_dict = {'status':'new', 'worker':''}
        if order['order_cycle_start'].date() + datetime.timedelta(days=3) == today:
            message_dict['message'] = MESSAGE_A
            if Shop.upsert_cs_message(nick, message_dict):
                print nick + ":" + message_dict['message']
        elif order['order_cycle_end'].date() == today + datetime.timedelta(days=3):
            message_dict['message'] = MESSAGE_B
            if Shop.upsert_cs_message(nick, message_dict):
                print nick + ":" + message_dict['message']
    logger.info('auto_support_script success')

def renew_account_script():
    try:
        renew_account_service()
    except Exception,e:
        logger.exception('renew_account_script error: %s', str(e))
        #send_sms('13738141586', 'renew_account_script error: %s' % (str(e)))
        send_sms(DIRECTOR['PHONE'], 'renew_account_script error: %s' % (str(e)))
    else:
        logger.info('renew_account_script ok')

def renew_account_service(_days = 4):
    """电话续费"""
    
    article_code_list = ['ts-1796606']
    today = datetime.date.today()
    renew_date = today - datetime.timedelta(days=_days)
    renew_time = datetime.datetime.combine(renew_date, datetime.time())
    article_nicks = collect_renew_nicks(renew_time, renew_time, article_code_list)
    for article_code in article_code_list:
        nick_list = article_nicks[article_code]
        report_date = today - datetime.timedelta(days=_days+1)
        file_name = CURRENT_DIR+'data/report_data/syb_report'+str(report_date)+'.csv'
        while not os.path.exists(file_name):
            report_date -= datetime.timedelta(days=1)
            file_name = CURRENT_DIR+'data/report_data/syb_report'+str(report_date)+'.csv'

        write_renew_report(file_name, nick_list)
        send_file = CURRENT_DIR+'data/renew_report.csv' 
        text = '需电话营销的用户报表测试版'
        #send_email_with_file('zhoujiebing@maimiaotech.com', text, str(renew_date)+'电话营销的用户报表', [send_file])
        send_email_with_file('chenlifen@maimiaotech.com', text, str(renew_date)+'电话营销的用户报表', [send_file])
        #send_email_with_file('xieguanfu@maimiaotech.com', text, str(renew_date)+'电话营销的用户报表', [send_file])
    logger.info('renew_account_script success')

if __name__ == '__main__':
    auto_support_script()
    #special_content_service()
    #special_content_service_new()
    #renew_account_service()
