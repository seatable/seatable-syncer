# config=utf-8
from flask_wtf import FlaskForm as Form
from wtforms import StringField, PasswordField, IntegerField, TextAreaField, SelectField
from wtforms.validators import DataRequired


class LoginForm(Form):
    username = StringField('username', validators=[DataRequired('username is null')])
    password = PasswordField('password', validators=[DataRequired('password is null')])


class AccountForm(Form):
    host = StringField('host', validators=[DataRequired('host is null')])
    user = StringField('user', validators=[DataRequired('user is null')])
    password = PasswordField('password', validators=[DataRequired('password is null')])
    port = IntegerField('port', validators=[DataRequired('port is null')])
    db_name = StringField('db_name', validators=[DataRequired('db_name is null')])
    db_type = SelectField('db_type', choices=('mysql',))


class QueryForm(Form):
    query = TextAreaField('query', validators=[DataRequired('query is null')])
