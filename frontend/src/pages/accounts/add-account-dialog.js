import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Modal, ModalHeader, ModalBody, ModalFooter, Button, FormGroup, Label, Input } from 'reactstrap';
import SeaTableSelect from '../../components/seatable-select';
import { ACCOUNT_TYPES } from './constants';

import '@/assets/css/add-account-dialog.css';

class AddAccountDialog extends Component {

  constructor(props) {
    super(props);
    this.createAccountTypeOptions();
    this.state = {
      isShowPassword: false,
      accountType: this.accountTypeOptions[0],
      host: '',
      user: '',
      password: '',
      port: 3306,
      accountName: '',
      error: ''
    };
  }

  createAccountTypeOptions = () => {
    this.accountTypeOptions = ACCOUNT_TYPES.map(accountType => {
      const { type, display } = accountType;
      return {
        value: type,
        label: <span>{display}</span>
      };
    });
  }

  toggle = () => {
    this.props.onToggle();
  }

  onSubmit = () => {
    const { accountType, host, user, password, port, accountName } = this.state;
    const data = {
      'account_type': accountType.value,
      'host': host ? host.trim() : '',
      'user': user ? user.trim() : '',
      'password': password ? password.trim() : '',
      'port': Number(port),
      'account_name': accountName ? accountName.trim() : ''
    };
    fetch('/api/v1/account/add/', {
      method: 'post',
      body: JSON.stringify(data),
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      mode: 'cors',
    }).then(res => res.json() ).then(data => {
      const { error, account } = data;
      if (error) {
        if (error === 'Session has expired') {
          location.href = location.origin + '/account/login/';
          return;
        }
        this.setState({ error });
      } else {
        this.props.onAddAccount(account);
        this.toggle();
      }
    }).catch(err => {
      this.setState({ error: 'Internal Server Error' });
    });
  }

  onAccountTypeChange = (option) => {
    if (option.value === this.state.accountType.value) return;
    this.setState({ accountType: option });
  }

  onHostChange = (event) => {
    const value = event.target.value;
    if (value === this.state.host) return;
    this.setState({ host: value });
  }

  onUserChange = (event) => {
    const value = event.target.value;
    if (value === this.state.user) return;
    this.setState({ user: value });
  }

  onPasswordChange = (event) => {
    const value = event.target.value;
    if (value === this.state.password) return;
    this.setState({ password: value });
  }

  onPortChange = (event) => {
    const value = event.target.value;
    if (value === this.state.port) return;
    this.setState({ port: value });
  }

  onAccountNameChange = (event) => {
    const value = event.target.value;
    if (value === this.state.accountName) return;
    this.setState({ accountName: value });
  }

  togglePassword = (event) => {
    event.stopPropagation();
    this.setState({ isShowPassword: !this.state.isShowPassword });
  }

  render() {
    const { accountType, host, user, password, port, accountName, isShowPassword, error } = this.state;
    const closeButton = (
      <div className="header-close-content" onClick={this.toggle}>
        <i className="dtable-font dtable-icon-x" onClick={this.toggle}></i>
      </div>
    );

    return (
      <Modal isOpen={true} toggle={this.toggle} className="add-account-dialog" style={{ height: window.innerHeight - 56 }}>
        <ModalHeader close={closeButton}>{'Add account'}</ModalHeader>
        <ModalBody className="add-account-content">
          <FormGroup>
            <Label>{'Account type'}</Label>
            <SeaTableSelect
              options={this.accountTypeOptions}
              value={accountType}
              onChange={this.onAccountTypeChange}
              menuPortalTarget={'#root'}
            />
          </FormGroup>
          <FormGroup>
            <Label>{'Host'}</Label>
            <Input value={host} onChange={this.onHostChange} />
          </FormGroup>
          <FormGroup>
            <Label>{'User'}</Label>
            <Input value={user} onChange={this.onUserChange} />
          </FormGroup>
          <FormGroup>
            <Label>{'Password'}</Label>
            <div className="account-password-input-content">
              <Input
                type={isShowPassword ? 'text' : 'password'}
                className='account-password-input'
                value={password}
                onChange={this.onPasswordChange}
              />
              <div className="eye-icon" onClick={this.togglePassword}>
                <i className={`dtable-font dtable-icon-eye${isShowPassword ? '' : '-slash'}`}></i>
              </div>
            </div>
          </FormGroup>
          <FormGroup>
            <Label>{'Port'}</Label>
            <Input type="number" value={port} onChange={this.onPortChange} min={0} step={1} />
          </FormGroup>
          <FormGroup>
            <Label>{'Account name'}</Label>
            <Input value={accountName} onChange={this.onAccountNameChange} />
          </FormGroup>
          <div className="add-account-error">{error}</div>
        </ModalBody>
        <ModalFooter>
          <Button color="secondary" onClick={this.toggle}>
            {'Cancel'}
          </Button>
          <Button
            color="primary"
            onClick={this.onSubmit}
            disabled={!accountType || !host || !user || !password || !port || !accountName}
          >
            {'Submit'}
          </Button>
        </ModalFooter>
      </Modal>
    );
  }
}

AddAccountDialog.propTypes = {
  onToggle: PropTypes.func.isRequired,
  onAddAccount: PropTypes.func.isRequired,
};

export default AddAccountDialog;
