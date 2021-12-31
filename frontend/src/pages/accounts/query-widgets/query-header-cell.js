import React, { Component } from 'react';
import PropTypes from 'prop-types';

const eventStopPropagation = (event) => {
  if (!event) return;
  event.stopPropagation();
  event.preventDefault && event.preventDefault();
  event.nativeEvent && event.nativeEvent.stopImmediatePropagation && event.nativeEvent.stopImmediatePropagation();
};

class QueryHeaderCell extends Component {

  constructor(props) {
    super(props);
    this.state = {
      isResizing: false,
      width: props.width || 200,
    };
  }

  onMouseDown = (event) => {
    eventStopPropagation(event);
    window.addEventListener('mousemove', this.onMouseMove);
    window.addEventListener('mouseup', this.onMouseUp);
    this.distance = {
      disX: event.clientX,
      width: this.state.width,
    };
    this.setState({ isResizing: true });
  }

  onMouseMove = (event) => {
    if (!this.state.isResizing) return;
    eventStopPropagation(event);
    const displacementX = event.clientX - this.distance.disX;
    if (displacementX === 0) return;
    let width = this.distance.width + Math.ceil(displacementX);
    if (width < 60) {
      width = 60;
    }
    this.setState({ width });
  }

  onMouseUp = (event) => {
    window.removeEventListener('mousemove', this.onMouseMove);
    window.removeEventListener('mouseup', this.onMouseUp);
    eventStopPropagation(event);
    if (!this.state.isResizing) return;
    this.props.onResize(this.state.width);
  }

  render() {
    const { display } = this.props;
    const { width } = this.state;
  
    return (
      <div
        className="query-account-result-cell"
        style={{ width }}
      >
        <div className="query-account-result-header-cell-content">{display}</div>
        <div className="resize-drag-handel" onMouseDown={this.onMouseDown}></div>
      </div>
    );
  }
}

QueryHeaderCell.propTypes = {
  width: PropTypes.number.isRequired,
  display: PropTypes.any,
  onResize: PropTypes.func,
};

export default QueryHeaderCell;
