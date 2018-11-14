from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from typing import List

import boto3
from airflow import configuration
from airflow.utils.log.logging_mixin import LoggingMixin
from botocore.exceptions import ClientError
from past.builtins import basestring

log = LoggingMixin().log


def send_raw_email(to, subject, html_content, files: List[str] = None,
                   dryrun=False, cc=None, bcc=None,
                   mime_subtype='mixed', mime_charset='utf-8',
                   **kwargs):
    region = os.environ.get('AIRFLOW_AWS_SES_REGION', 'eu-west-1')
    sender = configuration.conf.get('smtp', 'SMTP_MAIL_FROM')

    recipients = get_email_address_list(to)
    if cc:
        recipients = recipients + get_email_address_list(cc)
    if bcc:
        recipients = recipients + get_email_address_list(bcc)

    msg = build_mime_msg(sender, to, subject, html_content, files, cc,
                         mime_subtype, mime_charset)

    client = boto3.client('ses', region_name=region)

    if not dryrun:
        try:
            response = client.send_raw_email(
                Source=sender,
                Destinations=recipients,
                RawMessage={
                    'Data': msg.as_string(),
                }
            )
        except ClientError as e:
            log.error("Failed to send an email. %s", e.response['Error']['Message'])
        else:
            log.info("Sent an email to %s (msg_id: %s)", recipients, response.get('MessageId'))


def build_mime_msg(sender, to, subject, html_content, files=None, cc=None,
                   mime_subtype='mixed', mime_charset='utf-8'):
    msg = MIMEMultipart(mime_subtype)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ", ".join(get_email_address_list(to))

    if cc:
        msg['CC'] = ", ".join(get_email_address_list(cc))

    msg['Date'] = formatdate(localtime=True)
    htmlpart = MIMEText(html_content.encode(mime_charset), 'html', mime_charset)
    msg.attach(htmlpart)

    for fname in files or []:
        basename = os.path.basename(fname)
        with open(fname, "rb") as f:
            part = MIMEApplication(
                f.read(),
                Name=basename
            )
            part['Content-Disposition'] = 'attachment; filename="%s"' % basename
            part['Content-ID'] = '<%s>' % basename
            msg.attach(part)

    return msg


def ignore_all(to, subject, html_content, files=None,
               dryrun=False, cc=None, bcc=None,
               mime_subtype='mixed', mime_charset='utf-8',
               **kwargs):
    """
        Ignores all events and just logs them.
    """
    log.info("Alerting is turned OFF. Ignoring %s to %s.", subject, to)


def get_email_address_list(address_string):
    if isinstance(address_string, basestring):
        if ',' in address_string:
            address_string = address_string.split(',')
        elif ';' in address_string:
            address_string = address_string.split(';')
        else:
            address_string = [address_string]

    return address_string
