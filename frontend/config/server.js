'use strict';
// https://github.com/webpack/webpack-dev-server/blob/master/examples/api/simple/server.js

process.env.NODE_ENV = 'development';
process.env.BABEL_ENV = 'development';

// Makes the script crash on unhandled rejections instead of silently
// ignoring them. In the future, promise rejections that are not handled will
// terminate the Node.js process with a non-zero exit code.
process.on('unhandledRejection', err => {
  throw err;
});

// Ensure environment variables are read.
require('../config/env');

const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || '127.0.0.1';
const PUBLIC_PATH = process.env.PUBLIC_URL || 'http://127.0.0.1:3000/assets/';
const sockHost = process.env.WDS_SOCKET_HOST;
const sockPath = process.env.WDS_SOCKET_PATH; // default: '/sockjs-node'
const sockPort = process.env.WDS_SOCKET_PORT;

var webpack = require('webpack')
var WebpackDevServer = require('webpack-dev-server')
var configFactory = require('./webpack.config')
const { createCompiler } = require('react-dev-utils/WebpackDevServerUtils');

var config = configFactory('development');
const devSocket = {
  warnings: warnings =>
    devServer.sockWrite(devServer.sockets, 'warnings', warnings),
  errors: errors =>
    devServer.sockWrite(devServer.sockets, 'errors', errors),
}; 

const compiler = createCompiler({
  config,
  devSocket,
  webpack,
});

const devServerOptions = {
  hot: true,
  publicPath: PUBLIC_PATH,
  contentBase: '../assets',
  watchContentBase: true,
  historyApiFallback: true,
  sockHost,
  sockPath,
  sockPort,
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

const devServer = new WebpackDevServer(compiler, devServerOptions);
devServer.listen(PORT, HOST, function (err, result) {
  if (err) {
    console.log(err)
  }

  console.log(`Listening at ${HOST}:${PORT}`)
})
