// Copyright (C) 2026 C0 contributors; SPDX-License-Identifier: GPL-3.0-or-later
'use strict';
importScripts('./vendor/markdown-it-15.0.2.min.js');
self.onmessage=event=>{
  const parser=self.markdownit({html:false,linkify:false,typographer:false,maxNesting:32});
  self.postMessage({tokens:parser.parse(event.data,{})});
};
