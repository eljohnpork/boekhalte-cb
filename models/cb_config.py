# -*- coding: utf-8 -*-
"""
CB Berichttypen op jullie FTP:

CATALOGUS (dagelijks, ONIX 3 XML):
  ONIX3MCB   - CB assortiment (alle titels)
  ONIX3MCHB  - CBH Besteltitels
  ONIX3MEB   - EB assortiment (e-books)

VOORRAAD / BESCHIKBAARHEID:
  ABIAFN     - Beschikbaarheid 24/48u orders
  BHDART     - Beschikbaarheidsindicatoren per EAN (levertijdcodes)

ORDERS:
  NUITOP     - Niet uitgevoerde opdrachten
  OPNOPA     - Openstaande opdrachten afnemers
  UITOPD     - Uitgevoerde opdrachten

FINANCIEEL:
  DVFACBPDF  - Dienstverleningsfactuur PDF
  DVFACBUBL  - Dienstverleningsfactuur UBL 2.0
  REKOV      - Digitale rekeningenoverzichten (maandelijks)
  VERKPDF    - Digitale verkoopfacturen (ZIP/PDF)
  VERKUBL    - Digitale verkoopfacturen UBL 2.0
"""
import ftplib
import fnmatch
import logging
import os
import tempfile
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CbConfig(models.Model):
    _name = 'cb.config'
    _description = 'De Boekhalte CB FTP Configuratie'
    _rec_name = 'name'

    name = fields.Char(string='Naam', required=True, default='CB Configuratie')
    active = fields.Boolean(default=True)

    # FTP
    ftp_host = fields.Char(string='FTP Host', required=True)
    ftp_port = fields.Integer(string='FTP Poort', default=21)
    ftp_user = fields.Char(string='FTP Gebruikersnaam', required=True)
    ftp_password = fields.Char(string='FTP Wachtwoord', required=True)
    ftp_use_tls = fields.Boolean(string='Gebruik TLS/FTPS', default=True)
    ftp_base_path = fields.Char(string='Basispad FTP', default='/')

    # Catalogus berichten
    enable_onix3mcb = fields.Boolean('ONIX3MCB – CB assortiment', default=True)
    enable_onix3mchb = fields.Boolean('ONIX3MCHB – CBH Besteltitels', default=False)
    enable_onix3meb = fields.Boolean('ONIX3MEB – EB assortiment', default=False)

    # Beschikbaarheid
    enable_bhdart = fields.Boolean('BHDART – Beschikbaarheidsindicatoren', default=True)
    enable_abiafn = fields.Boolean('ABIAFN – Beschikbaarheid 24/48u', default=False)

    # Orders
    enable_uitopd = fields.Boolean('UITOPD – Uitgevoerde opdrachten', default=True)
    enable_nuitop = fields.Boolean('NUITOP – Niet uitgevoerde opdrachten', default=True)
    enable_opnopa = fields.Boolean('OPNOPA – Openstaande opdrachten', default=False)

    # Financieel
    enable_dvfacbubl = fields.Boolean('DVFACBUBL – Facturen UBL 2.0', default=True)
    enable_dvfacbpdf = fields.Boolean('DVFACBPDF – Facturen PDF', default=False)

    # Import instellingen
    default_supplier_id = fields.Many2one(
        'res.partner', string='CB als leverancier',
        domain=[('supplier_rank', '>', 0)]
    )
    default_product_categ_id = fields.Many2one(
        'product.category', string='Bovenliggende categorie'
    )
    create_missing_categories = fields.Boolean('NUR-categorieën auto-aanmaken', default=True)
    update_existing_products = fields.Boolean('Bestaande producten bijwerken', default=True)
    import_cover_images = fields.Boolean('Omslagafbeeldingen importeren', default=True)

    # Status
    last_catalog_sync = fields.Datetime('Laatste catalogus sync', readonly=True)
    last_stock_sync = fields.Datetime('Laatste voorraad sync', readonly=True)
    last_order_sync = fields.Datetime('Laatste order sync', readonly=True)
    last_invoice_sync = fields.Datetime('Laatste factuur sync', readonly=True)
    last_sync_created = fields.Integer('Aangemaakt', readonly=True)
    last_sync_updated = fields.Integer('Bijgewerkt', readonly=True)
    last_sync_errors = fields.Integer('Fouten', readonly=True)

    # ── Knoppen ──────────────────────────────────────────────────────────────

    def action_test_ftp_connection(self):
        self.ensure_one()
        try:
            ftp = self._get_ftp_connection()
            ftp.cwd(self.ftp_base_path or '/')
            listing = ftp.nlst()
            ftp.quit()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Verbinding OK!'),
                    'message': _('FTP verbonden. Mappen gevonden: %s') % ', '.join(listing[:10]),
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(_('FTP fout: %s') % str(e))

    def action_run_full_sync(self):
        self.ensure_one()
        wizard = self.env['cb.import.wizard'].create({
            'config_id': self.id, 'import_type': 'full',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cb.import.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_run_stock_sync(self):
        self.ensure_one()
        self._sync_bhdart()

    # ── Cron taken ────────────────────────────────────────────────────────────

    def _cron_sync_catalog(self):
        for c in self.search([('active', '=', True)]):
            try:
                c._sync_onix_catalog()
            except Exception as e:
                _logger.error('CB cron catalogus [%s]: %s', c.name, e)

    def _cron_sync_stock(self):
        for c in self.search([('active', '=', True)]):
            try:
                c._sync_bhdart()
            except Exception as e:
                _logger.error('CB cron voorraad [%s]: %s', c.name, e)

    def _cron_sync_orders(self):
        for c in self.search([('active', '=', True)]):
            try:
                c._sync_orders()
            except Exception as e:
                _logger.error('CB cron orders [%s]: %s', c.name, e)

    def _cron_sync_invoices(self):
        for c in self.search([('active', '=', True)]):
            try:
                c._sync_invoices()
            except Exception as e:
                _logger.error('CB cron facturen [%s]: %s', c.name, e)

    # ── FTP ──────────────────────────────────────────────────────────────────

    def _get_ftp_connection(self):
        self.ensure_one()
        ftp = ftplib.FTP_TLS() if self.ftp_use_tls else ftplib.FTP()
        ftp.connect(self.ftp_host, self.ftp_port, timeout=30)
        ftp.login(self.ftp_user, self.ftp_password)
        if self.ftp_use_tls:
            ftp.prot_p()
        return ftp

    def _get_ftp_files(self, ftp, subdir, pattern='*'):
        path = (self.ftp_base_path or '/').rstrip('/') + '/' + subdir
        try:
            ftp.cwd(path)
            files = ftp.nlst()
            if pattern != '*':
                files = [f for f in files if fnmatch.fnmatch(f, pattern)]
            return sorted(files), path
        except ftplib.error_perm:
            _logger.warning('CB FTP map niet gevonden: %s', path)
            return [], path

    def _download_to_tmp(self, ftp, path, filename):
        suffix = os.path.splitext(filename)[1] or '.tmp'
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            ftp.retrbinary('RETR ' + path.rstrip('/') + '/' + filename, tmp.write)
            tmp.close()
            return tmp.name
        except Exception:
            tmp.close()
            os.unlink(tmp.name)
            raise

    # ── Catalogus (ONIX3MCB / MCHB / MEB) ────────────────────────────────────

    def _sync_onix_catalog(self):
        self.ensure_one()
        feeds = []
        if self.enable_onix3mcb:
            feeds.append('ONIX3MCB')
        if self.enable_onix3mchb:
            feeds.append('ONIX3MCHB')
        if self.enable_onix3meb:
            feeds.append('ONIX3MEB')
        if not feeds:
            return

        log = self._create_log('catalog')
        total_c = total_u = total_e = 0
        try:
            ftp = self._get_ftp_connection()
            for feed in feeds:
                files, path = self._get_ftp_files(ftp, feed, '*.xml')
                _logger.info('CB %s: %d bestanden', feed, len(files))
                for fname in files:
                    tmp = self._download_to_tmp(ftp, path, fname)
                    try:
                        c, u, e = self._process_onix3_file(tmp, log)
                        total_c += c
                        total_u += u
                        total_e += e
                    finally:
                        os.unlink(tmp)
            ftp.quit()
        except Exception as e:
            log.write({'state': 'error', 'message': str(e)})
            raise

        self.write({
            'last_catalog_sync': fields.Datetime.now(),
            'last_sync_created': total_c,
            'last_sync_updated': total_u,
            'last_sync_errors': total_e,
        })
        log.write({
            'state': 'done',
            'products_created': total_c,
            'products_updated': total_u,
            'errors': total_e,
            'message': _('%d aangemaakt, %d bijgewerkt, %d fouten') % (total_c, total_u, total_e),
        })

    def _process_onix3_file(self, filepath, log):
        import xml.etree.ElementTree as ET
        created = updated = errors = 0
        try:
            tree = ET.parse(filepath)
        except ET.ParseError as e:
            raise UserError(_('Ongeldig ONIX XML: %s') % str(e))

        for elem in tree.getroot().iter('Product'):
            try:
                data = _parse_onix3_product(elem)
                if not data:
                    continue
                if self._upsert_product(data):
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors += 1
                _logger.debug('ONIX product fout: %s', e)
        return created, updated, errors

    # ── Beschikbaarheid (BHDART) ──────────────────────────────────────────────

    # CB levertijdcodes → werkdagen
    CB_AVAIL = {
        '01': 1, '02': 2, '03': 3, '04': 5, '05': 10,
        '06': 14, '07': 21, '08': 30, '09': 60, '10': 90,
        '20': 0, '30': 0, '99': 0,
    }

    def _sync_bhdart(self):
        self.ensure_one()
        if not self.enable_bhdart:
            return
        log = self._create_log('stock')
        updated = errors = 0
        try:
            ftp = self._get_ftp_connection()
            files, path = self._get_ftp_files(ftp, 'BHDART', '*.csv')
            if not files:
                files, path = self._get_ftp_files(ftp, 'BHDART', '*.txt')
            for fname in files:
                tmp = self._download_to_tmp(ftp, path, fname)
                try:
                    u, e = self._process_bhdart(tmp)
                    updated += u
                    errors += e
                finally:
                    os.unlink(tmp)
            ftp.quit()
        except Exception as e:
            log.write({'state': 'error', 'message': str(e)})
            return
        self.write({'last_stock_sync': fields.Datetime.now()})
        log.write({
            'state': 'done',
            'products_updated': updated,
            'errors': errors,
            'message': _('%d levertijden bijgewerkt') % updated,
        })

    def _process_bhdart(self, filepath):
        import csv
        updated = errors = 0
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            sample = f.read(2048)
            f.seek(0)
            sep = ';' if sample.count(';') > sample.count(',') else ','
            reader = csv.reader(f, delimiter=sep)
            for row in reader:
                if not row or row[0].startswith('#'):
                    continue
                try:
                    ean = row[0].strip()
                    code = row[1].strip() if len(row) > 1 else ''
                    days = self.CB_AVAIL.get(code, 7)
                    # Kolom 2 kan expliciete dagen bevatten
                    if len(row) > 2 and row[2].strip().isdigit():
                        days = int(row[2].strip())

                    product = self.env['product.product'].search(
                        [('barcode', '=', ean)], limit=1
                    )
                    if not product:
                        continue

                    if self.default_supplier_id:
                        si = self.env['product.supplierinfo'].search([
                            ('product_tmpl_id', '=', product.product_tmpl_id.id),
                            ('partner_id', '=', self.default_supplier_id.id),
                        ], limit=1)
                        if si:
                            si.write({'delay': days})
                        else:
                            self.env['product.supplierinfo'].create({
                                'product_tmpl_id': product.product_tmpl_id.id,
                                'partner_id': self.default_supplier_id.id,
                                'delay': days,
                            })
                    updated += 1
                except Exception:
                    errors += 1
        return updated, errors

    # ── Orders (UITOPD / NUITOP) ──────────────────────────────────────────────

    def _sync_orders(self):
        self.ensure_one()
        log = self._create_log('orders')
        updated = errors = 0
        try:
            ftp = self._get_ftp_connection()
            if self.enable_uitopd:
                files, path = self._get_ftp_files(ftp, 'UITOPD', '*.csv')
                for fname in files:
                    tmp = self._download_to_tmp(ftp, path, fname)
                    try:
                        u, e = self._process_uitopd(tmp)
                        updated += u
                        errors += e
                    finally:
                        os.unlink(tmp)
            if self.enable_nuitop:
                files, path = self._get_ftp_files(ftp, 'NUITOP', '*.csv')
                for fname in files:
                    tmp = self._download_to_tmp(ftp, path, fname)
                    try:
                        u, e = self._process_nuitop(tmp)
                        updated += u
                        errors += e
                    finally:
                        os.unlink(tmp)
            ftp.quit()
        except Exception as e:
            log.write({'state': 'error', 'message': str(e)})
            return
        self.write({'last_order_sync': fields.Datetime.now()})
        log.write({
            'state': 'done', 'products_updated': updated, 'errors': errors,
            'message': _('%d orders verwerkt') % updated,
        })

    def _process_uitopd(self, filepath):
        import csv
        updated = errors = 0
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            sep = ';' if f.read(1024).count(';') > f.read(1024).count(',') else ','
            f.seek(0)
            for row in csv.DictReader(f, delimiter=sep):
                try:
                    ref = row.get('OrderNummer') or row.get('Referentie') or ''
                    if not ref:
                        continue
                    po = self.env['purchase.order'].search(
                        [('partner_ref', '=', ref)], limit=1
                    )
                    if po:
                        po.message_post(body=_('CB bevestiging ontvangen (UITOPD): %s') % ref)
                        updated += 1
                except Exception:
                    errors += 1
        return updated, errors

    def _process_nuitop(self, filepath):
        import csv
        updated = errors = 0
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            sep = ';' if f.read(1024).count(';') > f.read(1024).count(',') else ','
            f.seek(0)
            for row in csv.DictReader(f, delimiter=sep):
                try:
                    ref = row.get('OrderNummer') or row.get('Referentie') or ''
                    reden = row.get('Reden') or row.get('NietUitgevoerdReden') or '?'
                    if not ref:
                        continue
                    po = self.env['purchase.order'].search(
                        [('partner_ref', '=', ref)], limit=1
                    )
                    if po:
                        po.message_post(
                            body=_('⚠️ CB: Order NIET uitgevoerd. Reden: %s') % reden
                        )
                        updated += 1
                except Exception:
                    errors += 1
        return updated, errors

    # ── Facturen (DVFACBUBL) ──────────────────────────────────────────────────

    def _sync_invoices(self):
        self.ensure_one()
        if not self.enable_dvfacbubl:
            return
        log = self._create_log('invoices')
        created = errors = 0
        try:
            ftp = self._get_ftp_connection()
            files, path = self._get_ftp_files(ftp, 'DVFACBUBL', '*.xml')
            for fname in files:
                tmp = self._download_to_tmp(ftp, path, fname)
                try:
                    if self._import_ubl_invoice(tmp):
                        created += 1
                finally:
                    os.unlink(tmp)
            ftp.quit()
        except Exception as e:
            log.write({'state': 'error', 'message': str(e)})
            return
        self.write({'last_invoice_sync': fields.Datetime.now()})
        log.write({
            'state': 'done',
            'products_created': created,
            'errors': errors,
            'message': _('%d facturen geïmporteerd') % created,
        })

    def _import_ubl_invoice(self, filepath):
        """Importeer UBL 2.0 factuur als vendor bill in Odoo."""
        import base64
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            journal = self.env['account.journal'].search(
                [('type', '=', 'purchase')], limit=1
            )
            if not journal:
                return False
            move = self.env['account.move'].create({
                'move_type': 'in_invoice',
                'journal_id': journal.id,
                'partner_id': self.default_supplier_id.id if self.default_supplier_id else False,
            })
            self.env['ir.attachment'].create({
                'name': os.path.basename(filepath),
                'datas': base64.b64encode(content),
                'res_model': 'account.move',
                'res_id': move.id,
                'mimetype': 'application/xml',
            })
            return True
        except Exception as e:
            _logger.warning('UBL import fout: %s', e)
            return False

    # ── Product upsert ────────────────────────────────────────────────────────

    def _upsert_product(self, data):
        isbn = (data.get('isbn') or '').strip()
        if not isbn:
            return False

        tmpl = self.env['product.template'].search([('barcode', '=', isbn)], limit=1)

        categ_id = self.default_product_categ_id.id if self.default_product_categ_id else False
        if data.get('nur_code') and self.create_missing_categories:
            cat = self._get_nur_category(data['nur_code'])
            if cat:
                categ_id = cat.id

        vals = {
            'name': data.get('title') or isbn,
            'barcode': isbn,
            'type': 'product',
            'sale_ok': True,
            'purchase_ok': True,
            'cb_authors': data.get('authors') or '',
            'cb_publisher': data.get('publisher') or '',
            'cb_nur_code': data.get('nur_code') or '',
            'cb_last_sync': fields.Datetime.now(),
            'description_sale': data.get('description') or '',
        }
        if categ_id:
            vals['categ_id'] = categ_id
        if data.get('list_price') is not None:
            vals['list_price'] = data['list_price']

        if tmpl:
            if self.update_existing_products:
                tmpl.write(vals)
            if self.import_cover_images and data.get('cover_url'):
                _set_cover(tmpl, data['cover_url'])
            return False

        new_tmpl = self.env['product.template'].create(vals)
        if self.import_cover_images and data.get('cover_url'):
            _set_cover(new_tmpl, data['cover_url'])
        if self.default_supplier_id:
            self.env['product.supplierinfo'].create({
                'product_tmpl_id': new_tmpl.id,
                'partner_id': self.default_supplier_id.id,
                'delay': 3,
            })
        return True

    def _get_nur_category(self, nur_code):
        nur = self.env['cb.nur.code'].search([('code', '=', nur_code)], limit=1)
        if nur and nur.product_categ_id:
            return nur.product_categ_id
        name = nur.name if nur else ('NUR ' + nur_code)
        domain = [('name', '=', name)]
        if self.default_product_categ_id:
            domain.append(('parent_id', '=', self.default_product_categ_id.id))
        cat = self.env['product.category'].search(domain, limit=1)
        if not cat:
            cat = self.env['product.category'].create({
                'name': name,
                'parent_id': self.default_product_categ_id.id if self.default_product_categ_id else False,
            })
        return cat

    def _create_log(self, sync_type):
        return self.env['cb.import.log'].create({
            'config_id': self.id,
            'sync_type': sync_type,
            'state': 'running',
        })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_onix3_product(elem):
    def get(tag):
        n = elem.find('.//' + tag)
        return n.text.strip() if n is not None and n.text else None

    isbn = get('IDValue') or get('b244')
    if not isbn or len(isbn) < 10:
        return None

    title = get('TitleText') or get('b203') or get('b202') or ''
    subtitle = get('Subtitle') or get('b029') or ''
    if subtitle:
        title = (title + ' - ' + subtitle).strip(' -')

    authors = []
    for c in elem.findall('.//Contributor'):
        for tag in ('PersonName', 'PersonNameInverted', 'KeyNames'):
            n = c.find('.//' + tag)
            if n is not None and n.text:
                authors.append(n.text.strip())
                break

    price = None
    for p in elem.findall('.//Price'):
        amt = p.find('.//PriceAmount') or p.find('.//j151')
        if amt is not None and amt.text:
            try:
                price = float(amt.text.strip().replace(',', '.'))
                break
            except ValueError:
                pass

    nur_code = None
    for s in elem.findall('.//Subject'):
        scheme = s.find('.//SubjectSchemeIdentifier') or s.find('.//b067')
        if scheme is not None and scheme.text in ('22', '65', '23'):
            cn = s.find('.//SubjectCode') or s.find('.//b069')
            if cn is not None and cn.text:
                nur_code = cn.text.strip()
                break

    cover_url = None
    for r in elem.findall('.//SupportingResource'):
        rtype = r.find('.//ResourceContentType') or r.find('.//x436')
        if rtype is not None and rtype.text == '01':
            ul = r.find('.//ResourceLink') or r.find('.//x435')
            if ul is not None and ul.text:
                cover_url = ul.text.strip()
                break

    desc = None
    for t in elem.findall('.//TextContent'):
        ttype = t.find('.//TextType') or t.find('.//x426')
        if ttype is not None and ttype.text in ('01', '02', '03', '13'):
            txt = t.find('.//Text') or t.find('.//d104')
            if txt is not None and txt.text:
                desc = txt.text.strip()
                break

    return {
        'isbn': isbn,
        'title': title or isbn,
        'authors': ', '.join(authors),
        'publisher': get('PublisherName') or get('b081') or '',
        'list_price': price,
        'nur_code': nur_code,
        'cover_url': cover_url,
        'description': desc,
    }


def _set_cover(product_tmpl, url):
    import urllib.request
    import base64
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            product_tmpl.write({'image_1920': base64.b64encode(r.read())})
    except Exception as e:
        _logger.debug('Cover fout (%s): %s', url, e)
