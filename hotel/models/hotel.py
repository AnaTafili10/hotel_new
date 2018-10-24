import base64
import logging

from odoo import api, fields, models
from odoo import tools, _
from odoo.exceptions import ValidationError, UserError
from odoo.osv import expression
from odoo.modules.module import get_module_resource
import datetime
import re


class Client(models.Model):
    _name = "hotel.client"
    _description = "client"

    identity_no = fields.Char(string="Identity Number", required=True)
    name = fields.Char(string="Name", required=True)
    surname = fields.Char(string="Surname", required=True)
    age = fields.Integer(string="Age", required=True)
    adr = fields.Char(string="Adr", required=True)
    phone = fields.Char(string="Phone", required=True)
    email = fields.Char(string="Email", required=True)
    active = fields.Boolean('Active', default=True, store=True)
    color = fields.Integer('Color Index', default=0)
    notes = fields.Text('Notes')
    reservation_ids = fields.One2many('reservation.room', 'client_ids', string="Reservation")
    room_ids = fields.One2many('hotel.room', 'client_ids', string="Room")
    reservation_client = fields.One2many('reservation.room', 'client_ids', string="Reservation")

    # image: all image fields are base64 encoded and PIL-supported
    image = fields.Binary(
        "Photo", default='_default_image', attachment=True,
        help="This field holds the image used as photo for the employee, limited to 1024x1024px.")
    image_medium = fields.Binary(
        "Medium-sized photo", attachment=True,
        help="Medium-sized photo of the employee. It is automatically "
             "resized as a 128x128px image, with aspect ratio preserved. "
             "Use this field in form views or some kanban views.")
    image_small = fields.Binary(
        "Small-sized photo", attachment=True,
        help="Small-sized photo of the employee. It is automatically "
             "resized as a 64x64px image, with aspect ratio preserved. "
             "Use this field anywhere a small image is required.")

    @api.model
    def _default_image(self):
        image_path = get_module_resource('hotel', 'static/src/img', 'default_image.png')
        return tools.image_resize_image_big(base64.b64encode(open(image_path, 'rb').read()))

   # Unicity_control
    _sql_constraints = [('identity_no_uniq', 'unique(identity_no)', "Identity number must be unique for every client"), ]

    # Control if identity number has 10 char
    @api.constrains('identity_no')
    def _nr_personal_length(self):
        if (len(self.identity_no) != 10):
            raise ValidationError("Identity number should be 10 char.")

    # Control if email adress is useful
    @api.constrains('email')
    def validate_email(self):
        if self.email:
            match =re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', self.email)
            if match == None:
                raise ValidationError('Please add an email adress.')

        # Control that phone field should contain numbers only
        @api.constrains('phone')
        def validate_phone(self):
            if self.phone:
                if not self.phone.isdigit():
                    raise ValidationError('Phone field should containt only digits.')

                def show_client(self, Context=None):
                    return {
                        'name': ('History'),
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_model': 'hotel.client',
                        'view_id': False,
                        'type': 'ir.actions.act_window',
                        'target': 'new',
                        'context': None,
                    }


class Floor(models.Model):
        _name = "hotel.floor"
        _description = "floor"
        _rec_name = "number"
        # name = fields.Char(string="Floor Name", required=True)
        number = fields.Integer(string="Floor")

class HotelRoom(models.Model):
    _name = 'hotel.room'
    _description = 'Hotel Room'

    name = fields.Char(string="Name", required=True)
    floor_id = fields.Many2one('hotel.floor', 'Floor No',
                               help='At which floor the room is located.')
    list_price = fields.Integer(string="Room rate")
    max_adult = fields.Integer('Max Adult')
    max_child = fields.Integer('Max Child')
    category_id = fields.Many2one('hotel.room.type', string='Room Category', required=True)
    status = fields.Selection([('available', 'Available'),
                               ('occupied', 'Occupied')],
                              'Status', default='available')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'), ('cancel', 'Cancel'), ('done', 'Done')],
                             'State', readonly=True, default=lambda *a: 'draft')
    capacity = fields.Integer('Capacity', required=True)
    # checkin_no = fields.Integer(compute ='checkin_no', string="Number of room checkin", store=True)
    client_ids = fields.Many2one('hotel.client', string="Client")
    reservation_ids = fields.One2many('reservation.room', 'room_ids')
    category_id = fields.Selection([('single', 'Single'), ('double', 'Double'), ('triple', 'Triple'), ('deluxe', 'Deluxe'), ('suite', 'Suite')], string="Room Type")

    def show_reservation(self, Context=None):
        return {
            'name': ('Reserve'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'reservation.room',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': None,
        }

    @api.constrains('capacity')
    def check_capacity(self):
        for room in self:
            if room.capacity <= 0:
                raise ValidationError(_('Room capacity must be more than 0'))

    @api.onchange('isroom')
    def isroom_change(self):
        '''
        Based on isroom, status will be updated.
        ----------------------------------------
        @param self: object pointer
        '''
        if self.isroom is False:
            self.status = 'occupied'
        if self.isroom is True:
            self.status = 'available'

    @api.multi
    def write(self, vals):
        """
        Overrides orm write method.
        @param self: The object pointer
        @param vals: dictionary of fields value.
        """
        if 'isroom' in vals and vals['isroom'] is False:
            vals.update({'color': 2, 'status': 'occupied'})
        if 'isroom' in vals and vals['isroom'] is True:
            vals.update({'color': 5, 'status': 'available'})
        ret_val = super(HotelRoom, self).write(vals)
        return ret_val

    @api.multi
    def set_room_status_occupied(self):
        """
        This method is used to change the state
        to occupied of the hotel room.
        ---------------------------------------
        @param self: object pointer
        """
        return self.write({'isroom': False, 'color': 2})

    @api.one
    def draft(self):
        self.state = 'draft'
        self.room_ids.state = 'Occupied'

    @api.one
    def available(self):
        self.state = 'Available'
        self.is_room()

    @api.one
    def cancel(self):
        self.state = 'cancel'
        self.cancel_room()

    @api.multi
    def set_room_status_available(self):
        """
        This method is used to change the state
        to available of the hotel room.
        ---------------------------------------
        @param self: object pointer
        """
        return self.write({'isroom': True, 'color': 5})


class RoomType(models.Model):
        _name = "hotel.room.type"
        _description = "Room Type"

        name = fields.Char(string="Name", required=True)
        category_id = fields.Many2one('hotel.room.type', 'Category')
        child_id = fields.One2many('hotel.room.type', 'category_id',
                                   'Child Categories')
        category_id = fields.Selection(
            [('single', 'Single'), ('double', 'Double'), ('triple', 'Triple'), ('deluxe', 'Deluxe'),
             ('suite', 'Suite')], string="Room Type")

        @api.multi
        def name_get(self):
            def get_names(cat):
                """ Return the list [cat.name, cat.category_id.name, ...] """
                res = []
                while cat:
                    res.append(cat.name)
                    cat = cat.categ_id
                return res

            return [(cat.id, " / ".join(reversed(get_names(cat)))) for cat in self]

        @api.model
        def name_search(self, name, args=None, operator='ilike', limit=100):
            if not args:
                args = []
            if name:
                # Be sure name_search is symetric to name_get
                category_names = name.split(' / ')
                parents = list(category_names)
                child = parents.pop()
                domain = [('name', operator, child)]
                if parents:
                    names_ids = self.name_search(' / '.join(parents), args=args,
                                                 operator='ilike', limit=limit)
                    category_ids = [name_id[0] for name_id in names_ids]
                    if operator in expression.NEGATIVE_TERM_OPERATORS:
                        categories = self.search([('id', 'not in', category_ids)])
                        domain = expression.OR([[('category_id', 'in',
                                                  categories.ids)], domain])
                    else:
                        domain = expression.AND([[('category_id', 'in',
                                                   category_ids)], domain])
                    for i in range(1, len(category_names)):
                        domain = [[('name', operator,
                                    ' / '.join(category_names[-1 - i:]))], domain]
                        if operator in expression.NEGATIVE_TERM_OPERATORS:
                            domain = expression.AND(domain)
                        else:
                            domain = expression.OR(domain)
                categories = self.search(expression.AND([domain, args]),
                                         limit=limit)
            else:
                categories = self.search(args, limit=limit)
            return categories.name_get()



class Reservation(models.Model):
    _name = 'reservation.room'
    _description = "Rezervimi i dhomes"

    reservation_ids = fields.Char(string="Reservation Nr", readonly=True)
    room_ids = fields.Many2one('hotel.room', string="Room")
    checkin = fields.Datetime('Expected-Date-Arrival', required=True, readonly=True, states={'draft': [('readonly', False)]})
    checkout = fields.Datetime('Expected-Date-Departure', required=True, readonly=True, states={'draft': [('readonly', False)]})
    reserve = fields.Many2many('hotel.room', 'room_ids','reservation.room', domain="[('isroom','=',True),\('category_id','=',category_id)]")
    category_id = fields.Many2one('hotel.room.type', 'Room Type')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'), ('cancel', 'Cancel'), ('done', 'Done')], 'State', readonly=True, default='draft')
    client_ids = fields.Many2one('hotel.client', string="Client")
    payed = fields.Boolean(string="Payed")
    reservation = fields.Boolean(string="Reservation", default=False)
    status = fields.Selection([('available', 'Available'),
                               ('occupied', 'Occupied')],
                              'Status', default='available')
    category_id = fields.Selection(
        [('single', 'Single'), ('double', 'Double'), ('triple', 'Triple'), ('deluxe', 'Deluxe'), ('suite', 'Suite')],
        string="Room Type")
    internet = fields.Boolean(string="Internet, Price:20")
    laundry = fields.Boolean(string="Laundry, Price:30")
    safe_box = fields.Boolean(string="Safe Box, Price:25")
    suitcase_storage = fields.Boolean(string="Suitcase Storage, Price:15")
    spa = fields.Boolean(string="Spa, Price:45")


    @api.model
    def create(self, vals):
        seq = self.env['ir.sequence'].next_by_code('reservation.room') or '/'
        vals['reservation_no'] = seq
        return super(Reservation, self).create(vals)


    @api.one
    def draft(self):
        self.state = 'draft'


    @api.one
    def done(self):
      self.state = 'done'
      for room in self:
        if room.room_ids:
            self.room_ids.write({'state': 'done'})


    @api.one
    def confirm(self):
        if self.payed == True:
            self.state = 'confirm'
            self.env['hotel.room'].write({'state': 'confirm'})
        else:
            raise ValidationError('You cant confirm reservation, unless you havent pay')


    @api.one
    def cancel(self):
        if self.state == 'confirm':
            current_date = datetime.date.today()
            if self.checkin:
              if self.checkin - current_date < '24':
                    raise ValidationError('User is not able to delete the \
    #                                                room after the room in %s state \
    #                                                in reservation')
            else:
                    self.state = 'cancel'
                    self.room_ids.write({'state': 'cancel'})

    @api.onchange('status')
    @api.multi
    def _get_total_price(self):
        for reservation in self:
            list_price = 0.0
            if reservation.room_ids:
                for room in reservation.room_ids:
                    list_price += room.list_price
            reservation.list_price_total = list_price

        # @api.multi
        # def draft_progressbar(self):
        #     self.ensure_one()
        #     self.write({
        #         'state': 'draft',
        #     })
        #
        #     @api.multi
        #     def confirm_progressbar(self):
        #         self.ensure_one()
        #         self.write({
        #             'state': 'confirm',
        #         })
        #
        #     @api.multi
        #     def cancel_progressbar(self):
        #         self.ensure_one()
        #         self.write({
        #             'state': 'cancel',
        #         })

        # Control if it has schedule crash, when it is uploding a new reservation
        @api.model
        def create(self, values):
            if values.get('room_ids', False) and values.get('checkin', False) and values.get('checkout',
                                                                                                 False):
                ids = self.search([('room_ids', '=', values['room_ids'])])
                if ids:
                    ids1 = ids.search(['&', ('checkin', '<=', values['checkin']),
                                       ('checkout', '>=', values['checkout'])])
                    ids2 = ids.search(['&', ('checkin', '<=', values['checkout']),
                                       ('checkout', '>=', values['checkout'])])
                    if (ids1 or ids2):
                        raise UserError(_("Room is accupied!"))
            return super(Reservation, self).create(values)

            # Control if it has schedule crash, when reservation is uploding
        @api.multi
        def write(self, vals):
            if vals.get('room_ids', False) and vals.get('checkin', False) and vals.get('checkout', False):
                wids = self.search([('room_ids', '=', vals['room_ids'])])
                if wids:
                    wids1 = wids.search(['&', ('checkin', '<=', vals['checkin']),
                                         ('checkout', '>=', vals['checkin'])])
                    wids2 = wids.search(['&', ('checkin', '<=', vals['checkout']),
                                         ('checkout', '>=', vals['checkout'])])
                    if (wids1 or wids2):
                        raise UserError(_("Room is not disponible at this time!"))
            return super(Reservation, self).write(vals)