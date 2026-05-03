const fs = require('fs');
const path = require('path');
const dir = './src/components/Dashboard';

fs.readdirSync(dir).forEach(file => {
  if (file.endsWith('.tsx')) {
    const filePath = path.join(dir, file);
    let content = fs.readFileSync(filePath, 'utf8');
    
    // Fix console logs colors
    content = content.replace(/text-gray-400 dark:text-white\/20 select-none/g, 'text-white/40 select-none');
    content = content.replace(/text-gray-600 dark:text-white\/60/g, 'text-white/60');
    
    // Fix buttons that became dark text but should be white because of dark backgrounds
    // bg-[color]-600 hover:bg-[color]-700 should have text-white
    content = content.replace(/(bg-\w+-600 hover:bg-\w+-700(.*?)shadow-\w+-600\/20) text-gray-900 dark:text-white/g, '$1 text-white');
    content = content.replace(/className="bg-yellow-600 hover:bg-yellow-700 shadow-lg shadow-yellow-600\/20 text-gray-900 dark:text-white/g, 'className="bg-yellow-600 hover:bg-yellow-700 shadow-lg shadow-yellow-600/20 text-white');
    content = content.replace(/className="bg-emerald-600 hover:bg-emerald-700 shadow-lg shadow-emerald-600\/20 text-gray-900 dark:text-white/g, 'className="bg-emerald-600 hover:bg-emerald-700 shadow-lg shadow-emerald-600/20 text-white');
    content = content.replace(/className="bg-purple-600 hover:bg-purple-700 shadow-lg shadow-purple-600\/20 min-w-\[140px\] text-gray-900 dark:text-white"/g, 'className="bg-purple-600 hover:bg-purple-700 shadow-lg shadow-purple-600/20 min-w-[140px] text-white"');
    
    // Safety check buttons
    content = content.replace(/text-gray-600 dark:text-white\/60 hover:text-red-400/g, 'text-gray-500 dark:text-white/60 hover:text-red-500 dark:hover:text-red-400');
    content = content.replace(/text-gray-600 dark:text-white\/60 hover:text-yellow-400/g, 'text-gray-500 dark:text-white/60 hover:text-yellow-600 dark:hover:text-yellow-400');
    content = content.replace(/text-gray-600 dark:text-white\/60 hover:text-purple-400/g, 'text-gray-500 dark:text-white/60 hover:text-purple-600 dark:hover:text-purple-400');

    // Discovery agent specific fix for the SVG rotation background
    content = content.replace(/bg-black\/60 p-6 font-mono/g, 'bg-gray-900 dark:bg-black/60 p-6 font-mono text-white/80');

    fs.writeFileSync(filePath, content);
    console.log('Fixed', file);
  }
});
