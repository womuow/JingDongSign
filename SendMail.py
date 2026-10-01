# -*- coding: utf-8 -*-
# Time    : Fri Jan 20 21:33:54 2023
# Author  : CuiMu
# E-mail  : 1006372551@qq.com
# Software: Spyder5
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr


def send_mail(theme, message, file, Tomail):
    "以QQ邮箱发送消息"
    msg = MIMEMultipart()
    msg.attach(MIMEText(message, "html", "utf-8"))
    msg["From"] = formataddr(["womuow", "womuow@qq.com"])
    msg["to"] = Tomail
    msg["Subject"] = theme

    # attach
    if file:
        attach = MIMEText(open(file, "rb").read(), "html", "utf-8")
        attach.add_header("Content-Disposition", "attachment", filename=file)
        msg.attach(attach)

    server = smtplib.SMTP_SSL("smtp.qq.com")
    server.login("womuow@qq.com", "sisxicqdnwsabbid")
    server.sendmail("womuow@qq.com", Tomail, msg.as_string())
    server.quit()
    print("Mail has Send!!")


if __name__ == "__main__":
    theme = "test"
    msg = "123456"
    Tomail = "womuow@139.com"  # "15732204398@139.com"
    send_mail(
        theme,
        msg,
        r"C:\PythonCode\my_awesome_util\test1.csv",
        Tomail,
    )
