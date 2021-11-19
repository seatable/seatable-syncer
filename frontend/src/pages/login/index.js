import React from 'react';
import PropTypes from 'prop-types';

const propTypes = {

};

class Login extends React.Component {

  render() {
    const loginUrl = 'account/login';

    return (
      <div className="container">
        {/* <form action={loginUrl} method="post">
          账号：{{ form.username() }}<label>{{ form.username.errors[0] }}</label><br/>
          密码：{{ form.password() }}<label>{{ form.hidden_tag() }}</label><br/>
          {% for msg in form.password.errors %}
          <div style="color:red" >{{msg}}</div>
          {% endfor %}
        <button type="submit">submit</button>
        </form> */}
        acdddkkkkddd你好的, 我是小强你好, 好的, 你是谁
      </div>
    );
  }
}

Login.propTypes = propTypes;

export default Login;
