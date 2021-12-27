import React from 'react';
import PropTypes from 'prop-types';

function AccountsFooter(props) {
  return (
    <div className="seatable-synchronizer-account-footer">
      {`${props.accountsCount} ${props.accountsCount > 1 ? 'accounts' : 'account'}`}  
    </div>
  );
}

AccountsFooter.propTypes = {
  accountsCount: PropTypes.number.isRequired
};

export default AccountsFooter;
