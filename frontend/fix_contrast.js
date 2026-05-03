const fs = require('fs');
const path = require('path');
const dir = './src/components/Dashboard';

fs.readdirSync(dir).forEach(file => {
  if (file.endsWith('.tsx')) {
    const filePath = path.join(dir, file);
    let content = fs.readFileSync(filePath, 'utf8');
    
    // Fix text contrast
    content = content.replace(/text-gray-400/g, 'text-gray-500'); // Make gray-400 darker in light mode
    content = content.replace(/text-gray-500/g, 'text-gray-600'); // Make gray-500 darker
    
    // Colored text contrast in light mode
    ['blue', 'emerald', 'yellow', 'red', 'purple', 'orange'].forEach(color => {
      // Find `text-{color}-400` without dark prefix and make it `text-{color}-600 dark:text-{color}-400`
      const regex = new RegExp(`(?<!dark:)text-${color}-400`, 'g');
      content = content.replace(regex, `text-${color}-700 dark:text-${color}-400`);
      
      // Also fix background of badges if they use 500/10, they need a bit more contrast in light mode maybe?
      // Actually bg-{color}-100 dark:bg-{color}-500/10
      const bgRegex = new RegExp(`(?<!dark:)bg-${color}-500/10`, 'g');
      content = content.replace(bgRegex, `bg-${color}-50 dark:bg-${color}-500/10`);
      
      const borderRegex = new RegExp(`(?<!dark:)border-${color}-500/20`, 'g');
      content = content.replace(borderRegex, `border-${color}-200 dark:border-${color}-500/20`);
      
      const border30Regex = new RegExp(`(?<!dark:)border-${color}-500/30`, 'g');
      content = content.replace(border30Regex, `border-${color}-300 dark:border-${color}-500/30`);
    });

    // Fix card contrast
    content = content.replace(/bg-white dark:bg-white\/5/g, 'bg-white dark:bg-white/5');
    // Ensure all borders are gray-200
    content = content.replace(/border-gray-100/g, 'border-gray-200');

    // Make sure SVG and icon strokes have enough contrast
    content = content.replace(/text-white\/40/g, 'text-gray-500 dark:text-white/40'); // catch any missed ones

    fs.writeFileSync(filePath, content);
    console.log('Fixed contrast', file);
  }
});
