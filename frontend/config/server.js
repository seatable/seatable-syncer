'use strict';
// https://github.com/webpack/webpack-dev-server/blob/master/examples/api/simple/server.js

process.env.NODE_ENV = 'development';
process.env.BABEL_ENV = 'development';

// Ensure environment variables are read.
require('../config/env');

const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || '127.0.0.1';
const PUBLIC_PATH = process.env.PUBLIC_URL || 'http://127.0.0.1:3000/assets/';

var Webpack = require('webpack')
var WebpackDevServer = require('webpack-dev-server')
var configFactory = require('./webpack.config')
var config = configFactory('development');

const compiler = Webpack(config);
const devServerOptions =  {
  hot: true,
  publicPath: PUBLIC_PATH,
  contentBase: '../assets',
  watchContentBase: true,
  historyApiFallback: true,
  headers: {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
    "Access-Control-Allow-Headers": "X-Requested-With, content-type, Authorization"
  },
  stats: {
    colors: true
  }
};

console.log('Dev server options:', devServerOptions);

const server = new WebpackDevServer(compiler, devServerOptions);
server.listen(PORT, HOST, function (err, result) {
  if (err) {
    console.log(err)
  }

  console.log(`Listening at ${HOST}:${PORT}`)
})
