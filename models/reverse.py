# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

from datetime import date
from datetime import datetime
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import calendar
import re
import json
from dateutil.relativedelta import relativedelta
import pgeocode
import qrcode
from PIL import Image
from random import choice
from string import digits
import json
import re
import uuid
from functools import partial


class Pdccheque(models.Model):
    _inherit = "pdc.cheque.collection"

    def _compute_status_compute(self):
        for each in self:
            if len(each.partner_invoices.filtered(lambda a: a.state == 'deposit')) > 0:
                each.status_compute = True
            else:
                each.status_compute = False



class CreditLimitRecord(models.Model):
    _inherit = "credit.limit.record"


    @api.onchange('date')
    def onchange_date(self):
        if self.date:
            months = self.env['credit.limit.configuration'].search([('active', '=', True)]).months
            percentage = self.env['credit.limit.configuration'].search([('active', '=', True)]).percentage
            min_credit_amt = self.env['credit.limit.configuration'].search([('active', '=', True)]).min_credit_amount
            from_month = datetime.today().date() - relativedelta(months=months)
            to_month = datetime.today().date()
            list = []

            for partner_wise in self.env['partner.ledger.customer'].search(
                    [('company_id', '=', 1), ('date', '>=', from_month), ('date', '<=', to_month),
                     ('debit', '!=', 0)]).filtered(lambda a: a.debit >= 1).mapped('partner_id'):
                avg_amt = 0
                for each in sorted(self.env['partner.ledger.customer'].search(
                        [('company_id', '=', 1), ('date', '>=', from_month), ('date', '<=', to_month),
                         ('partner_id', '=', partner_wise.id)])):
                    avg_amt += each.debit
                    balance = each.balance
                value = percentage / 100
                aveg_amount = avg_amt / months
                basic_value = aveg_amount * value
                print(partner_wise, 'partner_wise')
                credit_amount = 0
                if min_credit_amt > basic_value:
                    credit_amount = min_credit_amt
                else:
                    credit_amount = basic_value

                line = (0, 0, {
                    'partner_id': each.partner_id.id,
                    'balance': balance,
                    'average_amount': aveg_amount,
                    'credit_limit_amount': basic_value,
                    'min_credit_amount': credit_amount
                })
                list.append(line)
            self.credit_limit_lines = list


class DataEntryLine(models.Model):
    _inherit = "data.entry.line"

    vehicle_id = fields.Many2one('fleet.vehicle',string="Vehicle Id")



class AreaCustomersOther(models.Model):
    _inherit = 'areas.customers.other'

    @api.depends('collected_amount')
    def _compute_balance(self):
        for line in self:
            line.balance =0.0
            if line.out_standing_balance:
                line.balance = line.out_standing_balance - line.collected_amount

class AreaCustomersFilter(models.Model):
    _inherit = 'areas.filter.lines'

    @api.depends('collected_amount')
    def _compute_balance(self):
        for line in self:
            line.balance =0.0
            if line.out_standing_balance:
                line.balance = line.out_standing_balance - line.collected_amount


class SalesPersonTarget(models.Model):
    _inherit = "sales.person.target"
    _order = "id desc, name desc"


    @api.depends('target_lines', 'target_lines.target_qty', 'target_lines.target_amount',
                 'target_lines.achievement_percentage', 'target_lines.achievement_amount')
    def _compute_all_targets(self):
        for each_month in self:
            each_month.target = sum(each_month.target_lines.mapped('target_qty'))
            each_month.target_amount = sum(each_month.target_lines.mapped('target_amount'))
            each_month.achievement = sum(each_month.target_lines.mapped('achievement_qty'))
            each_month.achievement_amount = sum(each_month.target_lines.mapped('achievement_amount'))
            each_month.difference_amount = sum(each_month.target_lines.mapped('achievement_amount'))
            each_month.achievement_percentage = 0
            each_month.difference = sum(each_month.target_lines.mapped('target_qty')) - sum(
                each_month.target_lines.mapped(
                    'achievement_qty'))
            each_month.difference_amount = sum(each_month.target_lines.mapped(
                'target_amount')) - sum(each_month.target_lines.mapped('achievement_amount'))
            # if each_month.achievement:
            #     each_month.achievement_percentage = (each_month.achievement/each_month.target)*100

class TargetLines(models.Model):
    _inherit = "target.lines"

    @api.depends('achievement_amount', 'achievement_qty')
    def _compute_all_targets(self):
        for each_month in self:
            each_month.achievement_percentage = 0
            each_month.achievement_amount_percentage = 0
            each_month.pending_qty = 0
            if each_month.achievement_qty:
                each_month.pending_qty = each_month.target_qty - each_month.achievement_qty
                if each_month.target_qty:
                   each_month.achievement_percentage = (each_month.achievement_qty / each_month.target_qty) * 100
            else:
                each_month.achievement_percentage = 0
                each_month.pending_qty = 0

            if each_month.achievement_amount:
                each_month.pending_amount = each_month.target_amount - each_month.achievement_amount
                if each_month.target_amount:
                    each_month.achievement_amount_percentage = (each_month.achievement_amount / each_month.target_amount) * 100
            else:
                each_month.achievement_amount_percentage = 0
                each_month.pending_amount = 0




class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('including_price','taxes_id','product_qty')
    def onchange_including_price(self):
        if self.including_price:
            tax = 0
            if self.freight_charge:
                self.including_price = self.including_price-self.freight_charge

            for each in self.taxes_id:
                if each.children_tax_ids:
                    for ch in each.children_tax_ids:
                        tax += ch.amount
                else:
                    tax += each.amount
            if self.order_id.partner_id.tcs == True:
                value = 100 + tax +0.128
            else:
                value = 100 + tax
            basic_value = self.including_price * 100 / value
            # basic_value = basic_value
            t= basic_value/self.product_qty
            # self.price_unit = t -0.00002
            self.price_unit = t

