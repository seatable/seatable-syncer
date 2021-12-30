import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Button } from 'reactstrap';
import isHotkey from 'is-hotkey';
import QueryHeaderCell from './query-widgets/query-header-cell';
import Loading from '../../components/loading';

import '@/assets/css/query-account.css';

class QueryAccount extends Component {

  constructor(props) {
    super(props);
    this.state = {
      isClosing: false,
      searchValue: '',
      errorMsg: '',
      results: '',
      columnWidthMap: {},
      isQuerying: false,
    };
  }

  onToggle = () => {
    this.setState({ isClosing: true }, () => {
      setTimeout(() => {
        this.props.toggle();
      }, 300);
    });
  }

  onSearchValueChange = (event) => {
    const value = event.target.value;
    if (value === this.state.searchValue) return;
    this.setState({ searchValue: value });
  }

  onKeyDown = (event) => {
    if (isHotkey('enter', event)) {
      this.onQuery();
    }
  }

  onQuery = () => {
    const validSearchValue = this.state.searchValue.trim();
    if (!validSearchValue) return;
    this.queryInputRef.blur();
    this.setState({ isQuerying: true });
    const { account } = this.props;
    fetch(`/api/v1/account/${account.id}/query/`, {
      method: 'post',
      body: JSON.stringify({query: validSearchValue }),
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      mode: 'cors',
    }).then(res => res.json()).then(res => {
      const { error_msg, results } = res;
      if (error_msg) {
        if (error_msg === 'Session has expired') {
          location.href = location.origin + '/account/login/';
          return;
        }
        this.setState({ errorMsg: error_msg, isQuerying: false, results: [] });
      } else {
        
        let columnWidthMap = { 'index': 80 };
        if (Array.isArray(results) && results.length > 0) {
          Object.keys(results[0]).forEach(key => {
            columnWidthMap[key] = 200;
          });
        }
        this.setState({ errorMsg: '', results, columnWidthMap, isQuerying: false });
      }
    }).catch(err => {
      this.setState({ errorMsg: 'Internal Server Error', isQuerying: false, results: [] });
    });
  }

  resizeCellWidth = (key, width) => {
    const { columnWidthMap } = this.state;
    this.setState({ columnWidthMap: Object.assign({}, columnWidthMap, { [key]: width }) });
  }

  renderResult = () => {
    const { errorMsg, results, columnWidthMap, isQuerying } = this.state;
    if (isQuerying) {
      return (
        <div className="query-account-loading">
          <Loading />
        </div>
      );
    }
    if (errorMsg) {
      return (
        <div className="query-account-error">{errorMsg}</div>
      );
    }
    if (Array.isArray(results) && results.length > 0) {
      const keys = Object.keys(results[0]);
      const totalWidth = Object.values(columnWidthMap).reduce((prev, curr) => prev + curr, 0);
      return (
        <div className="query-account-results">
          <div className='query-account-results-container' style={{ width: totalWidth > window.innerWidth - 32 - 2 ? '100%' : 'fit-content' }}>
            <div className="query-account-results-content" style={{ width: totalWidth }}>
              <div className="query-account-results-header">
                <div className="query-account-result-row">
                  <div
                    className="query-account-result-cell query-account-result-index-cell"
                    style={{ width: columnWidthMap['index'] }}
                  ></div>
                  {keys.map(key => {
                    return (
                      <QueryHeaderCell
                        key={`header-row-cell-${key}`}
                        width={columnWidthMap[key]}
                        display={key}
                        onResize={(width) => this.resizeCellWidth(key, width)}
                      />
                    );
                  })}
                </div>
              </div>
              <div className="query-account-results-body">
                {results.map((result, index) => {
                  return (
                    <div className="query-account-result-row" key={`result-row-${index}`}>
                      <div
                        className="query-account-result-cell query-account-result-index-cell"
                        style={{ width: columnWidthMap['index'] }}
                      >
                        {index + 1}
                      </div>
                      {keys.map(key => {
                        const value = result[key];
                        return (
                          <div
                            key={`result-cell-${index}-${key}`}
                            className="query-account-result-cell"
                            title={value}
                            style={{ width: columnWidthMap[key] }}
                          >
                            {value}
                          </div>);
                      })}
                    </div>
                  );
                })}
              </div>
              <div className="query-account-results-footer">
                <div className="query-account-results-count">{`${results.length} ${results.length > 1 ? 'records' : 'record'}`}</div>
              </div>
            </div>
          </div>
        </div>
      );
    }

    if (Array.isArray(results) && results.length === 0) {
      return (
        <div className="query-account-results-none">
          {'No results'}
        </div>
      );
    }
    return null;
  }

  render() {
    const { isClosing, searchValue } = this.state;
    const { account } = this.props;

    return (
      <div className={`query-account ${isClosing ? 'closing-query-account' : ''}`}>
        <div className="query-account-header">
          <div className="query-account-header-name">{account.account_name}</div>
          <div className="query-account-header-close" onClick={this.onToggle}>
            <i className="dtable-font dtable-icon-x"></i>
          </div>
        </div>
        <div className="query-account-body">
          <div className="query-account-query-container">
            <input
              className="sql-input form-control"
              value={searchValue}
              onChange={this.onSearchValueChange}
              onKeyDown={this.onKeyDown}
              ref={ref => this.queryInputRef = ref}
            />
            <Button color="primary" className="query-button" onClick={this.onQuery} disabled={!searchValue || !searchValue.trim()} >
              {'Query'}
            </Button>
          </div>
          {this.renderResult()}
        </div>
      </div>
    );
  }
}

QueryAccount.propTypes = {
  account: PropTypes.object.isRequired,
  toggle: PropTypes.func.isRequired,
};

export default QueryAccount;
