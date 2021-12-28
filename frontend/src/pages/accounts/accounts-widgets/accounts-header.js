import React from 'react';
import { ACCOUNT_ATTRIBUTE_DISPLAY } from '../constants';

export default function AccountsHeader() {
  return (
    <div className="seatable-synchronizer-account-header">
      <div className="seatable-synchronizer-account-row">
        <div className="seatable-synchronizer-account-cell seatable-synchronizer-account-index-cell"></div>
        {ACCOUNT_ATTRIBUTE_DISPLAY.map(attribute => {
          const value = attribute.name;
          return (
            <div key={`account-header-${attribute.key}`} className="seatable-synchronizer-account-cell" title={value}>{value}</div>
          );
        })}
        <div className="seatable-synchronizer-account-cell seatable-synchronizer-account-query-cell"></div>
      </div>
    </div>
  );
}
