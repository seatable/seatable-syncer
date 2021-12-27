import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { ACCOUNT_ATTRIBUTE_DISPLAY } from '../constants';

class AccountsBody extends Component {

  render() {
    const { accounts } = this.props; 

    return (
      <div className="seatable-synchronizer-account-body">
        <div className="seatable-synchronizer-accounts-content">
          {accounts.map((account, idx) => {
            return (
              <div key={`account-row-${account.id}`} className="seatable-synchronizer-account-row">
                <div className="seatable-synchronizer-account-cell seatable-synchronizer-account-index-cell">{idx + 1}</div>
                {ACCOUNT_ATTRIBUTE_DISPLAY.map(attribute => {
                  const value = account[attribute.key];
                  return (
                    <div
                      key={`account-row-cell-${account.id}-${attribute.key}`}
                      className="seatable-synchronizer-account-cell"
                      title={value}
                    >
                      {value}
                    </div>
                  );
                })}
                <div
                  className="seatable-synchronizer-account-cell seatable-synchronizer-account-query-cell"
                  onClick={() => this.props.onQueryToggle(account)}
                >
                  {'Query'}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
}

AccountsBody.propTypes = {
  accounts: PropTypes.array,
  onQueryToggle: PropTypes.func.isRequired,
};

export default AccountsBody;
