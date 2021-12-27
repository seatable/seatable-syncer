import React, { Component, Fragment } from 'react';
import ReactDOM from 'react-dom';
import Account from './model';
import AddAccountDialog from './add-account-dialog';
import AccountsHeader from './accounts-widgets/accounts-header';
import AccountsBody from './accounts-widgets/accounts-body';
import AccountsFooter from './accounts-widgets/accounts-footer';
import QueryDatabase from './query';

import '@/assets/css/accounts.css';

const { error, accounts } = window.app.config;
const newAccounts = Array.isArray(accounts)
  ? accounts.map(account => new Account(account))
  : [];

class Accounts extends Component {

  constructor(props) {
    super(props);
    this.state = {
      isShowAddAccountDialog: false,
      isShowQueryPlugin: false,
      queryAccount: '',
      accounts: newAccounts,
    };
  }

  onAddAccountToggle = () => {
    this.setState({ isShowAddAccountDialog: !this.state.isShowAddAccountDialog });
  }

  onAddAccount = (account) => {
    let { accounts } = this.state;
    let newAccounts = accounts.slice(0);
    newAccounts.push(new Account(account));
    this.setState({ accounts: newAccounts });
  }

  onQueryToggle = (account) => {
    if (account) {
      this.setState({ queryAccount: account, isShowQueryPlugin: true });
      return;
    }
    this.setState({ isShowQueryPlugin: false, queryAccount: null });
  }

  render() {
    if (error) {
      return (
        <div className="seatable-synchronizer-accounts-error">
          {error}
        </div>
      );
    }

    const { isShowAddAccountDialog, isShowQueryPlugin, queryAccount, accounts } = this.state;
    return (
      <Fragment>
        <div className="seatable-synchronizer-accounts">
          <div className="seatable-synchronizer-accounts-header">
            <button type="button" className="btn btn-secondary operation-item btn btn-secondary" onClick={this.onAddAccountToggle}>
              {'Add account'}
            </button>
          </div>
          <div className="seatable-synchronizer-accounts-container">
            <AccountsHeader />
            <AccountsBody accounts={accounts} onQueryToggle={this.onQueryToggle} />
            <AccountsFooter accountsCount={accounts.length} />
          </div>
        </div>
        {isShowAddAccountDialog && (
          <AddAccountDialog
            onToggle={this.onAddAccountToggle}
            onAddAccount={this.onAddAccount}
          />
        )}
        {isShowQueryPlugin && (
          <QueryDatabase
            account={queryAccount}
            toggle={this.onQueryToggle}
          />
        )}
      </Fragment>
    );
  }
}

ReactDOM.render(
  <React.Suspense>
    <Accounts />
  </React.Suspense>,
  document.getElementById('root')
);
