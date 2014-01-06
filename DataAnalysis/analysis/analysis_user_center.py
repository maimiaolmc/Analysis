#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
@author: zhoujiebin
@contact: zhoujiebing@maimiaotech.com
@date: 2012-12-10 17:13
@version: 0.0.0
@license: Copyright maimiaotech.com
@copyright: Copyright maimiaotech.com

"""
import os
import sys
import time
if __name__ == '__main__':
    sys.path.append('../../')

import datetime
from CommonTools.logger import logger
from CommonTools.send_tools import send_sms, send_email_with_text, DIRECTOR
from CommonTools.wangwang_tools import parse_wangwang_talk_record
from DataAnalysis.conf.settings import CURRENT_DIR
from user_center.conf.settings import WORKER_DICT, FULL_NUM
from user_center.services.shop_db_service import ShopDBService
from user_center.services.order_db_service import OrderDBService
from user_center.services.refund_db_service import RefundDBService
from user_center.services.support_db_service import SupportDBService
from DataAnalysis.analysis.analysis_campaign_complex import analysis_campaign_complex

class UserCenter:

    def __init__(self):
        self.time_now = datetime.datetime.now()
        self.code_name = {'ts-1796606':'省油宝', 'ts-1797607':'选词王', 'ts-1817244':'淘词'}
        self.order_type = {1:'新订', 2:'续订', 3:'升级', 4:'后台赠送', 5:'后台自动续订'}
         
    def collect_online_info(self):
        """获取用户数据中心信息"""
        
        #获取所有用户
        all_shop = ShopDBService.get_all_shop_list()
        self.nick_shop = {}        
        for shop in all_shop:
            self.nick_shop[shop['nick']] = shop
        
        #获取所有退款
        self.all_refund = RefundDBService.get_all_refunds_list()
        refund_ids = set([refund['order_id'] for refund in self.all_refund])
        
        #获取所有订单
        all_order = OrderDBService.get_all_orders_list()
        #user_ok_orders 排除退款
        self.user_ok_orders = {}
        self.user_all_orders = {}

        for order in all_order:
            key = (order['nick'], order['article_code'])
            if not self.user_all_orders.has_key(key):    
                self.user_all_orders[key] = []
            self.user_all_orders[key].append(order)
        
        for key in self.user_all_orders.keys():
            real_orders = []
            ok_orders = []
            orders = self.user_all_orders[key]
            orders.sort(key=lambda order:order['order_cycle_start'])
            for i in range(len(orders)):
                order = orders[i]
                if int(order['total_pay_fee']) > 500 or i == 0:
                    if i < len(orders) - 1:
                        next_order = orders[i+1]
                        #合并 优惠 续费 订单
                        if int(next_order['total_pay_fee']) <= 500 and next_order['biz_type'] == 2:
                            order['order_cycle_end'] = next_order['order_cycle_end']
                    ok_orders.append(order)
                    if order['order_id'] not in refund_ids:
                        real_orders.append(order)
            self.user_ok_orders[key] = ok_orders
            self.user_all_orders[key] = real_orders
    
    def analysis_out_of_date_num(self, start_time, end_time, article_code_list):
        """到期用户分析"""
        
        return_str = '近7天到期用户数统计:\n'
        return_str += '日期,省油宝,北斗\n'
        num_effect = {}
        start_date = start_time.date()
        while start_date <= end_time.date():
            num_effect[start_date] = {}
            for article_code in article_code_list:
                num_effect[start_date][article_code] = 0
            start_date += datetime.timedelta(days=1)

        for key in self.user_ok_orders.keys():
            orders = self.user_ok_orders[key]
            article_code = key[1]
            if not article_code in article_code_list:
                continue
            if len(orders) <= 0:
                continue
            order = orders[-1]
            if start_time <= order['order_cycle_end'] <= end_time:
                deadline = order['order_cycle_end'].date()
                num_effect[deadline][article_code] += 1
        date_list = num_effect.keys()
        date_list.sort()
        for date in date_list:
            return_str += '%s: %d, %d\n' % (str(date), num_effect[date]['ts-1796606'],\
                    num_effect[date]['ts-1797607'])
        return return_str

    def analysis_worker_arrange(self):
        """专属客服分配情况"""
        
        return_str = '每个专属客服配置的最大服务客户数为%d.\n' % (FULL_NUM)
        for worker_id in WORKER_DICT.keys():
            number = ShopDBService.count_normal_allocated_shop(worker_id)
            return_str += '麦苗科技 %s : %d\n' % (WORKER_DICT[worker_id], number)

        return return_str

    def analysis_renew_report(self, file_date):
        """配合analysis_orders_renew使用"""
        
        file_name = CURRENT_DIR+('/data/report_data/syb_report%s.csv' % str(file_date))
        sucess_content = analysis_campaign_complex(file_name, '省油宝', self.success_nick_list)
        fail_content = analysis_campaign_complex(file_name, '省油宝', self.fail_nick_list)
        print sucess_content
        print '--------------------------'
        print fail_content
        import random
        nick_list = random.sample(self.fail_nick_list, 20)
        for nick in nick_list:
            print nick

    def analysis_orders_renew(self, start_time, end_time, article_code_list):
        """续费率统计"""
        
        self.success_nick_list = []
        self.fail_nick_list = []

        some_days = [-10, -3, 0, 3, 7, 10]
        some_day_count = {}
        success_count = {}
        fail_count = {}
        for key in article_code_list:
            success_count[key] = 0
            fail_count[key] = 0
            for days in some_days:
                some_day_count[(key,days)] = 0 
        for key in self.user_ok_orders.keys():
            orders = self.user_ok_orders[key]
            article_code = key[1]
            if not article_code in article_code_list:
                continue
            for i in range(len(orders)):
                deadline = orders[i]['order_cycle_end']
                if deadline >= start_time and deadline <= end_time:
                    
                    if i < len(orders) - 1:
                        success_count[article_code] += 1
                        delay_days = (orders[i+1]['create'] - deadline).days
                        for days in some_days:
                            if delay_days > days:
                                continue
                            some_day_count[(article_code, days)] += 1
                        self.success_nick_list.append(orders[i]['nick'])

                    else:
                        fail_count[article_code] += 1
                        self.fail_nick_list.append(orders[i]['nick'])

                    break
                elif deadline > end_time:
                    break
        return_str = ''
        header = '产品,统计开始时间,统计结束时间,过期用户数,截止当下的续费数,续费率\n'
        some_days_str = ','.join([str(day)+'天续费' for day in some_days]) + '\n'
        
        for key in article_code_list:
            fail_num = success_count[key]+fail_count[key]
            success_percent = float(success_count[key]) / fail_num
            report = '%s, %s, %s, %d, %d, %.2f\n' % (self.code_name[key], \
                    str(start_time.date()), str(end_time.date()), fail_num, \
                    success_count[key], success_percent)
            
            report1 = []
            report2 = []
            for i in range(len(some_days)):
                days = some_days[i]
                days_count = some_day_count[(key, days)]
                report2.append('%.2f' % (float(days_count) / fail_num))
                if i > 0:
                    days = some_days[i-1]
                    days_count -= some_day_count[(key, days)]
                report1.append(str(days_count))
            return_str += header
            return_str += report
            return_str += some_days_str
            return_str += ','.join(report1)+'\n'
            return_str += ','.join(report2)+'\n'
        
        return return_str
    
    def analysis_worker_refund(self, start_time, end_time, article_code):
        """退款统计"""

        pass

    def analysis_pre_market(self, start_time, end_time, article_code_list, file_name):
        """售前营销统计"""
        
        start_date = start_time.date()
        end_date = end_time.date()
        (worker_list, wangwang_records) = parse_wangwang_talk_record(file_name, \
                start_date, end_date)
        pre_market_effect = {}
        for worker in worker_list:
            pre_market_effect[worker] = {}
            pre_market_effect[worker]['sum_pay'] = 0
            pre_market_effect[worker]['success_count'] = 0
            pre_market_effect[worker]['service_num'] = 0
        success_data = {}
        for key in wangwang_records:
            success_data[key] = {}
            for article_code in article_code_list:
                success_data[key][article_code] = set([])

        #计算成功的转化
        for key in self.user_all_orders:
            nick = str(key[0])
            article_code = str(key[1])
            orders = self.user_all_orders[key]
            if article_code not in article_code_list or len(orders) == 0:
                continue
            for i in range(len(orders)):    
                create_time = orders[i]['create']
                create_date = create_time.date()
                #订单发生时间在 统计时间内
                if start_date <= create_date <= end_date:
                    wangwang_record = wangwang_records[create_date]
                    #获取那天和该客户聊天的客服
                    workers = wangwang_record.get(nick, [])
                    if i > 0:
                        #非新客户，前面已有订单
                        if orders[i]['biz_type'] != 1:
                            #不是新订单
                            continue
                        elif create_date <= orders[i-1]['order_cycle_end'].date() + \
                                datetime.timedelta(days=15):
                            #是新订单 但未超过15天
                            continue
                    success_data[create_date][article_code].add(nick)
                    for worker in workers:
                        pre_market_effect[worker]['sum_pay'] += \
                                    float(orders[i]['total_pay_fee']) / 100.0 / len(workers)
                        pre_market_effect[worker]['success_count'] += 1

                elif create_date > end_date:
                    break
        
        #计算服务数量
        for date in wangwang_records:
            wangwang_record = wangwang_records[date]
            success_nick = success_data[date]
            for service_nick in wangwang_record:
                flag = True
                check_article_code = []
                for article_code in article_code_list:
                    #如果该nick在那天买了article_code,那只看article_code
                    if service_nick in success_nick[article_code]:
                        check_article_code.append(article_code)
                if len(check_article_code) == 0:
                    #如果用户啥都没买，那就都看看
                    check_article_code.extend(article_code_list)

                for article_code in check_article_code:
                    key = (service_nick.decode('utf-8'), article_code)
                    orders = self.user_all_orders.get(key, [])
                    if len(orders) > 0:
                        before_orders = filter(lambda order:order['create'].date() < date, orders)
                        if len(before_orders) > 0:
                            if before_orders[-1]['order_cycle_end'].date() >= date:
                                #过滤date 当天没过期的老客户
                                flag = False
                                continue
                            if len(orders) == len(before_orders) and \
                                    before_orders[-1]['order_cycle_end'].date() \
                                        + datetime.timedelta(days=15) >= date:
                                #过滤date 时 过期未超过15 天
                                flag = False
                                continue
                if flag:
                    workers = wangwang_record[service_nick]
                    for worker in workers:
                        pre_market_effect[worker]['service_num'] += 1

        for key in pre_market_effect:
            pre_market_effect[key]['renew'] = pre_market_effect[key]['success_count'] /\
                    (pre_market_effect[key]['service_num']+0.01)
        return pre_market_effect

    def analysis_phone_renew(self, start_time, end_time, article_code):
        """电话营销统计 月末统计上个月倒数第15天到本月倒数第16天"""

        phone_renew_effect = {}
        #目前就一个电话营销
        worker_num = 1
        for key in range(worker_num):
            phone_renew_effect[key] = {'fail_count':0, 'success_count':0, 'sum_pay':0}

        for key in self.user_ok_orders.keys():
            orders = self.user_ok_orders[key]
            if key[1] != article_code:
                continue
            worker_id = hash(key[0]) % worker_num
            for i in range(len(orders)):    
                deadline = orders[i]['order_cycle_end']
                create_time = orders[i]['create']
                
                #续费率 使用到期时间
                if start_time <= deadline <= end_time:
                    if i < len(orders) - 1:
                        start_date = deadline + datetime.timedelta(days=4)
                        end_date = deadline + datetime.timedelta(days=15)
                        
                        if start_date <= orders[i+1]['create'] <= end_date:
                            phone_renew_effect[worker_id]['success_count'] += 1
                            continue
                    phone_renew_effect[worker_id]['fail_count'] += 1
                #提成 使用发生时间
                if start_time <= create_time <= end_time:
                    if i > 0:
                        start_date = orders[i-1]['order_cycle_end'] + datetime.timedelta(days=4)
                        end_date = orders[i-1]['order_cycle_end'] + datetime.timedelta(days=15)
                        if start_date <= create_time <= end_date:
                            phone_renew_effect[worker_id]['sum_pay'] += \
                                    int(orders[i]['total_pay_fee']) / 100
                elif create_time > end_time:
                    break

        for key in range(worker_num):
            phone_renew_effect[key]['renew'] = phone_renew_effect[key]['success_count'] / (phone_renew_effect[key]['fail_count']+0.01)
        return phone_renew_effect

    def analysis_worker_renew2(self, start_time, end_time, article_code):
        """续费率统计 月末统计上个月倒数第3天到本月倒数第4天"""
       
        worker_renew_effect = {}
        workers = WORKER_DICT.keys() + [-1]
        for key in workers:
            worker_renew_effect[key] = {'fail_count':0, 'success_count':0, 'sum_pay':0}
        
        for key in self.user_ok_orders.keys():
            orders = self.user_ok_orders[key]
            if key[1] != article_code:
                continue
            shop = self.nick_shop.get(key[0], None)
            #无主订单
            if not shop:
                worker_id = -1
            else:
                worker_id = shop['worker_id']
            for i in range(len(orders)):    
                deadline = orders[i]['order_cycle_end']
                create_time = orders[i]['create']
                #续费率 使用到期时间 
                if start_time <= deadline <= end_time:
                    if worker_id == -1:
                        logger.info('%s find order, but not find shop' % key[0])
                    if i < len(orders) - 1:  
                        if orders[i+1]['create'] <= deadline + datetime.timedelta(days=3):
                            worker_renew_effect[worker_id]['success_count'] += 1
                    worker_renew_effect[worker_id]['fail_count'] += 1
                #提成 使用发生时间
                if start_time <= create_time <= end_time:
                    if i > 0:
                        if create_time <= orders[i-1]['order_cycle_end'] + datetime.timedelta(days=3):
                            worker_renew_effect[worker_id]['sum_pay'] += int(orders[i]['total_pay_fee']) / 100
                elif create_time > end_time:
                    break
        
        for key in workers:
            worker_renew_effect[key]['renew'] = worker_renew_effect[key]['success_count'] / (worker_renew_effect[key]['fail_count']+0.01)

        return worker_renew_effect

    def analysis_orders_statistics(self):
        """统计订单类型"""
        
        price_type = [0 for i in range(8)]
        first_type = {}
        second_type = {}
        more_type = [0 for i in range(6)]
        
        cycle_type = [u"1个月", u"12个月", u"6个月", u"3个月", u"0个月" ]
        for key in cycle_type:
            first_type[key] = 0
            second_type[key] = 0
            
        order_count = 0
        for key in self.user_ok_orders.keys():
            orders = self.user_ok_orders[key]
            for i in range(len(orders)):
                order = orders[i]
                if i == 0:
                    first_type[order['order_cycle']] += 1
                    fee = int(order['total_pay_fee']) / 100
                    price_type[fee / 100] += 1
                    order_count += 1

                elif i == 1:
                    second_type[order['order_cycle']] += 1

                more_type[i] += 1
            
            if order_count > 10000:
                break
        print '首次订购价格'
        price_sum = sum(price_type)
        for i in range(len(price_type)):
            print '%d~%d: %d, %.4f' % (i*100, i*100+100, price_type[i], float(price_type[i])/price_sum)
        print '合计:', price_sum

        print '第一次订购周期'
        cycle_sum = sum(first_type.values())
        for key in cycle_type:
            print '%s, %d, %.3f' % (key, first_type[key], float(first_type[key])/cycle_sum)
        print '合计:', cycle_sum

        print '第二次订购周期'
        cycle_sum = sum(second_type.values())
        for key in cycle_type:
            print '%s, %d, %.3f' % (key, second_type[key], float(second_type[key])/cycle_sum)
        print '合计:',cycle_sum

        print '重复订购情况'
        more_sum = sum(more_type)
        for i in range(len(more_type)):
            print '订购%d次, %d, %.3f' % (i+1, more_type[i], float(more_type[i])/more_sum)
        print '合计:',more_sum 

def daily_report_script():
    """日常订单统计报表"""
    
    today = datetime.datetime.combine(datetime.date.today(), datetime.time())
    daily_report_date = today - datetime.timedelta(days=1)
    try:
        user_obj = UserCenter()
        user_obj.collect_online_info()
        return_str = user_obj.analysis_orders_renew(daily_report_date, daily_report_date, ['ts-1796606'])
        return_str += user_obj.analysis_worker_arrange()
        return_str += user_obj.analysis_out_of_date_num(today, today+datetime.timedelta(days=6),\
                ['ts-1796606', 'ts-1797607'])
        #send_email_with_text(DIRECTOR['EMAIL'], return_str, 'UserCenter统计')
        #send_email_with_text('zhangfenfen@maimiaotech.com', return_str, 'UserCenter统计')
        #send_email_with_text('tangxijin@maimiaotech.com', return_str, 'UserCenter统计')
        send_email_with_text('product@maimiaotech.com', return_str, 'UserCenter统计')
    except Exception,e:
        logger.exception('daily_report_script error: %s' % (str(e)))
        send_sms(DIRECTOR['PHONE'], 'daily_report_script error: %s' % (str(e)))
    else:
        logger.info('daily_report_script ok')


def cycle_report_script(file_name=''):
    """周期统计报表"""
    
    user_obj = UserCenter()
    user_obj.collect_online_info()
    
    print '售前绩效分析'
    print '客服,成交额,成功数,服务数,寻单转化率'
    pre_market_effect = user_obj.analysis_pre_market(datetime.datetime(2013,5,31,0,0), \
            datetime.datetime(2013,6,27,0,0), ['ts-1796606', 'ts-1797607'], file_name)
    for worker in pre_market_effect:
        effect = pre_market_effect[worker]
        print '%s, %.1f, %d, %d, %.3f' % (worker, effect['sum_pay'], \
            effect['success_count'], effect['service_num'], effect['renew'])
    
    print '售后绩效分析'
    print '专属客服,成交额,成功数,过期数,续费率'
    worker_renew_effect = user_obj.analysis_worker_renew2(datetime.datetime(2013,5,28,0,0),  \
            datetime.datetime(2013,6,14,0,0), 'ts-1796606')
    for worker_id in worker_renew_effect:
        effect = worker_renew_effect[worker_id]
        if worker_id > -1:
            print '%s, %d, %d, %d, %.3f' % (WORKER_DICT[worker_id], effect['sum_pay'], \
                effect['success_count'], effect['fail_count'], effect['renew'])
        else:
            print '其他, %d, %d, %d, %.3f' % (effect['sum_pay'], \
                effect['success_count'], effect['fail_count'], effect['renew'])
    
    print '电销绩效分析'
    print 'id,成交额,成功数,过期数,续费率'
    phone_renew_effect = user_obj.analysis_phone_renew(datetime.datetime(2013,11,1,0,0), \
            datetime.datetime(2013,11,30,0,0), 'ts-1796606')
    for id in phone_renew_effect:
        effect = phone_renew_effect[id]
        print '%d, %d, %d, %d, %.3f' % (id, effect['sum_pay'],\
                effect['success_count'], effect['fail_count'], effect['renew'])


def special_report_script():
    """日常订单统计报表"""
    
    user_obj = UserCenter()
    user_obj.collect_online_info()
    return_str = user_obj.analysis_orders_renew(datetime.datetime(2013,6,1,0,0), \
            datetime.datetime(2013,6,8,0,0), ['ts-1796606'])
    print return_str

if __name__ == '__main__':
    daily_report_script()
    #cycle_report_script(CURRENT_DIR + 'data/wangwang_record.csv')
    #user_obj = UserCenter()
    #user_obj.collect_online_info()
    #return_str = user_obj.analysis_orders_renew(datetime.datetime(2013,6,1,0,0), \
            #        datetime.datetime(2013,6,30,23,59), ['ts-1796606'])
    #print return_str
    #user_obj.analysis_renew_report(datetime.date(2013,7,2))
    #daily_report_script()
    #print user_obj.analysis_pre_market(datetime.datetime(2013,7,1,0,0), datetime.datetime(2013,7,30,0,0), ['ts-1796606'],CURRENT_DIR + 'data/wangwang_0701_0715.csv')
