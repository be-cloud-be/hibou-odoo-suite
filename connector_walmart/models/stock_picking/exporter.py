# -*- coding: utf-8 -*-
# © 2017 Hibou Corp.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.addons.component.core import Component
from odoo.addons.queue_job.exception import NothingToDoJob
from logging import getLogger

_logger = getLogger(__name__)


class WalmartPickingExporter(Component):
    _name = 'walmart.stock.picking.exporter'
    _inherit = 'walmart.exporter'
    _apply_on = ['walmart.stock.picking']

    def _get_args(self, binding, lines):
        sale_binder = self.binder_for('walmart.sale.order')
        walmart_sale_id = sale_binder.to_external(binding.walmart_order_id)
        return walmart_sale_id, lines

    def _get_lines(self, binding):
        """
        Normalizes picking line data into the format to export to Walmart.
        :param binding: walmart.stock.picking
        :return: list[ dict(number, amount, carrier, methodCode, trackingNumber, trackingUrl=None) ]
        """
        ship_date = binding.date_done
        # in ms
        ship_date_time = int(fields.Datetime.from_string(ship_date).strftime('%s')) * 1000
        lines = []
        for line in binding.move_lines:
            sale_line = line.procurement_id.sale_line_id
            if not sale_line.walmart_bind_ids:
                continue
            # this is a particularly interesting way to get this,
            walmart_sale_line = next(
                (line for line in sale_line.walmart_bind_ids
                 if line.backend_id.id == binding.backend_id.id),
                None
            )
            if not walmart_sale_line:
                continue

            number = walmart_sale_line.walmart_number
            amount = 1 if line.product_qty > 0 else 0
            carrier = binding.carrier_id.walmart_carrier_code
            methodCode = binding.walmart_order_id.shipping_method_code
            trackingNumber = binding.carrier_tracking_ref
            trackingUrl = None
            lines.append(dict(
                shipDateTime=ship_date_time,
                number=number,
                amount=amount,
                carrier=carrier,
                methodCode=methodCode,
                trackingNumber=trackingNumber,
                trackingUrl=trackingUrl,
            ))

        return lines

    def run(self, binding):
        """
        Export the picking to Walmart
        :param binding: walmart.stock.picking
        :return:
        """

        if binding.external_id:
            return 'Already exported'
        lines = self._get_lines(binding)
        if not lines:
            raise NothingToDoJob('Cancelled: the delivery order does not contain '
                                 'lines from the original sale order.')
        args = self._get_args(binding, lines)
        external_id = self.backend_adapter.create(*args)
        self.binder.bind(external_id, binding)
