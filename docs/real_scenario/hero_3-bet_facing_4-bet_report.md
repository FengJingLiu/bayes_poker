# Hero_3-Bet_Facing_4-Bet 场景测试报告

总耗时: 79738.0ms

## 数据不足 (<50手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R14:4% RAI:0% | F:94% C:4% R:2% | 3.53% | 2.14% | 0.7776 | F:42% C:32% R35:5% RAI:20% | F:45% C:35% R35:4% RAI:16% | 11.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R14:4% RAI:0% | F:93% C:4% R:2% | 3.61% | 2.28% | 0.7954 | F:41% C:33% R35:6% RAI:20% | F:44% C:35% R35:5% RAI:16% | 11.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R20:3% RAI:0% | F:94% C:4% R:2% | 2.78% | 2.41% | 0.9313 | F:53% C:29% R33:0% RAI:18% | F:53% C:30% R33:0% RAI:17% | 11.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R19:3% RAI:0% | F:93% C:5% R:2% | 2.93% | 2.43% | 0.9103 | F:51% C:31% R33:0% RAI:18% | F:52% C:32% R33:0% RAI:16% | 12.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:95% C:0% R13.1:5% RAI:0% | F:93% C:4% R:2% | 4.57% | 2.28% | 0.7073 | F:41% C:34% R35:7% RAI:19% | F:45% C:37% R35:5% RAI:13% | 11.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R17.5:3% RAI:1% | F:94% C:4% R:2% | 2.68% | 2.41% | 0.9484 | F:52% C:31% R33:0% RAI:17% | F:53% C:31% R33:0% RAI:16% | 11.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R17.5:3% RAI:1% | F:93% C:5% R:2% | 2.92% | 2.43% | 0.9125 | F:51% C:32% R33:0% RAI:17% | F:52% C:32% R33:0% RAI:16% | 12.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:95% C:0% R21:5% RAI:1% | F:94% C:4% R:2% | 4.57% | 2.41% | 0.7267 | F:56% C:26% R35:0% RAI:18% | F:59% C:28% R35:0% RAI:13% | 11.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:94% C:0% R20:5% RAI:0% | F:93% C:5% R:2% | 5.18% | 2.43% | 0.6846 | F:52% C:30% R33:0% RAI:18% | F:56% C:32% R33:0% RAI:12% | 12.0 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% C:0% R20:2% RAI:1% | F:93% C:5% R:2% | 1.97% | 2.43% | 1.1115 | F:44% C:29% R40:0% RAI:27% | F:42% C:27% R40:0% RAI:31% | 12.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:95% C:0% R13.1:5% RAI:0% | F:93% C:4% R:2% | 4.57% | 2.28% | 0.7073 | F:39% C:37% R33:6% RAI:18% | F:43% C:40% R33:4% RAI:13% | 11.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R17.5:3% RAI:1% | F:94% C:4% R:2% | 2.68% | 2.41% | 0.9484 | F:53% C:30% R34:0% RAI:17% | F:53% C:31% R34:0% RAI:16% | 11.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R17.5:3% RAI:1% | F:93% C:5% R:2% | 2.92% | 2.43% | 0.9125 | F:52% C:30% R34:0% RAI:18% | F:53% C:30% R34:0% RAI:16% | 12.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:95% C:0% R21:5% RAI:1% | F:94% C:4% R:2% | 4.57% | 2.41% | 0.7267 | F:57% C:26% R35:0% RAI:17% | F:60% C:28% R35:0% RAI:12% | 11.7 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:94% C:0% R20:5% RAI:0% | F:93% C:5% R:2% | 5.18% | 2.43% | 0.6846 | F:52% C:32% R33:0% RAI:16% | F:55% C:34% R33:0% RAI:11% | 12.2 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% C:0% R20:2% RAI:1% | F:93% C:5% R:2% | 1.97% | 2.43% | 1.1115 | F:40% C:34% R38:1% RAI:25% | F:39% C:33% R38:1% RAI:28% | 12.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:95% C:0% R21:5% RAI:1% | F:94% C:4% R:2% | 4.57% | 2.41% | 0.7267 | F:56% C:26% R40:0% RAI:17% | F:60% C:28% R40:0% RAI:12% | 11.9 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:94% C:0% R20:5% RAI:0% | F:93% C:5% R:2% | 5.18% | 2.43% | 0.6846 | F:57% C:23% R40:0% RAI:20% | F:61% C:25% R40:0% RAI:14% | 12.0 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% C:0% R20:2% RAI:1% | F:93% C:5% R:2% | 1.97% | 2.43% | 1.1115 | F:52% C:18% R45:0% RAI:30% | F:49% C:17% R45:0% RAI:33% | 12.8 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% C:0% R20:2% RAI:1% | F:93% C:5% R:2% | 1.97% | 2.43% | 1.1115 | F:36% C:37% R40:0% RAI:27% | F:34% C:36% R40:0% RAI:30% | 12.4 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | elvq | 12 | 16.7% | 16.7% | F:96% R14:4% RAI:0% | F:95% C:3% R:3% | 3.53% | 2.59% | 0.8563 | F:42% C:32% R35:5% RAI:20% | F:44% C:34% R35:4% RAI:17% | 214.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:96% R14:4% RAI:0% | F:92% C:5% R:4% | 3.61% | 3.76% | 1.0212 | F:41% C:33% R35:6% RAI:20% | F:41% C:33% R35:6% RAI:20% | 220.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R20:3% RAI:0% | F:91% C:5% R:4% | 2.78% | 4.33% | 1.2479 | F:53% C:29% R33:0% RAI:18% | F:50% C:28% R33:0% RAI:23% | 215.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R19:3% RAI:0% | F:89% C:5% R:6% | 2.93% | 5.63% | 1.3861 | F:51% C:31% R33:0% RAI:18% | F:46% C:28% R33:0% RAI:25% | 219.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:95% C:0% R13.1:5% RAI:0% | F:92% C:5% R:4% | 4.57% | 3.76% | 0.9081 | F:41% C:34% R35:7% RAI:19% | F:42% C:35% R35:6% RAI:17% | 218.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:96% R17.5:3% RAI:1% | F:91% C:5% R:4% | 2.68% | 4.33% | 1.2708 | F:52% C:31% R33:0% RAI:17% | F:50% C:29% R33:0% RAI:21% | 218.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:96% R17.5:3% RAI:1% | F:89% C:5% R:6% | 2.92% | 5.63% | 1.3894 | F:51% C:32% R33:0% RAI:17% | F:47% C:29% R33:0% RAI:24% | 217.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:95% C:0% R21:5% RAI:1% | F:91% C:5% R:4% | 4.57% | 4.33% | 0.9738 | F:56% C:26% R35:0% RAI:18% | F:56% C:26% R35:0% RAI:17% | 220.3 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:94% C:0% R20:5% RAI:0% | F:89% C:5% R:6% | 5.18% | 5.63% | 1.0423 | F:52% C:30% R33:0% RAI:18% | F:52% C:29% R33:0% RAI:19% | 216.7 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% C:0% R20:2% RAI:1% | F:89% C:5% R:6% | 1.97% | 5.63% | 1.6924 | F:44% C:29% R40:0% RAI:27% | F:32% C:21% R40:1% RAI:46% | 217.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:95% C:0% R13.1:5% RAI:0% | F:92% C:5% R:4% | 4.57% | 3.76% | 0.9081 | F:39% C:37% R33:6% RAI:18% | F:40% C:38% R33:6% RAI:16% | 217.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:96% R17.5:3% RAI:1% | F:91% C:5% R:4% | 2.68% | 4.33% | 1.2708 | F:53% C:30% R34:0% RAI:17% | F:50% C:29% R34:0% RAI:21% | 218.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:96% R17.5:3% RAI:1% | F:89% C:5% R:6% | 2.92% | 5.63% | 1.3894 | F:52% C:30% R34:0% RAI:18% | F:48% C:27% R34:0% RAI:25% | 218.5 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:95% C:0% R21:5% RAI:1% | F:91% C:5% R:4% | 4.57% | 4.33% | 0.9738 | F:57% C:26% R35:0% RAI:17% | F:57% C:27% R35:0% RAI:16% | 217.8 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:94% C:0% R20:5% RAI:0% | F:89% C:5% R:6% | 5.18% | 5.63% | 1.0423 | F:52% C:32% R33:0% RAI:16% | F:51% C:32% R33:0% RAI:17% | 217.9 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% C:0% R20:2% RAI:1% | F:89% C:5% R:6% | 1.97% | 5.63% | 1.6924 | F:40% C:34% R38:1% RAI:25% | F:30% C:26% R38:1% RAI:43% | 217.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:95% C:0% R21:5% RAI:1% | F:91% C:5% R:4% | 4.57% | 4.33% | 0.9738 | F:56% C:26% R40:0% RAI:17% | F:57% C:27% R40:0% RAI:17% | 220.9 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:94% C:0% R20:5% RAI:0% | F:89% C:5% R:6% | 5.18% | 5.63% | 1.0423 | F:57% C:23% R40:0% RAI:20% | F:56% C:23% R40:0% RAI:21% | 221.0 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% C:0% R20:2% RAI:1% | F:89% C:5% R:6% | 1.97% | 5.63% | 1.6924 | F:52% C:18% R45:0% RAI:30% | F:36% C:13% R45:0% RAI:51% | 218.0 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% C:0% R20:2% RAI:1% | F:89% C:5% R:6% | 1.97% | 5.63% | 1.6924 | F:36% C:37% R40:0% RAI:27% | F:27% C:28% R40:0% RAI:45% | 222.6 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R14:4% RAI:0% | F:94% C:4% R:2% | 3.53% | 2.14% | 0.7776 | F:42% C:32% R35:5% RAI:20% | F:45% C:35% R35:4% RAI:16% | 11.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R14:4% RAI:0% | F:93% C:4% R:2% | 3.61% | 2.28% | 0.7954 | F:41% C:33% R35:6% RAI:20% | F:44% C:35% R35:5% RAI:16% | 11.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R20:3% RAI:0% | F:94% C:4% R:2% | 2.78% | 2.41% | 0.9313 | F:53% C:29% R33:0% RAI:18% | F:53% C:30% R33:0% RAI:17% | 11.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R19:3% RAI:0% | F:93% C:5% R:2% | 2.93% | 2.43% | 0.9103 | F:51% C:31% R33:0% RAI:18% | F:52% C:32% R33:0% RAI:16% | 12.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:95% C:0% R13.1:5% RAI:0% | F:93% C:4% R:2% | 4.57% | 2.28% | 0.7073 | F:41% C:34% R35:7% RAI:19% | F:45% C:37% R35:5% RAI:13% | 12.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R17.5:3% RAI:1% | F:94% C:4% R:2% | 2.68% | 2.41% | 0.9484 | F:52% C:31% R33:0% RAI:17% | F:53% C:31% R33:0% RAI:16% | 11.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R17.5:3% RAI:1% | F:93% C:5% R:2% | 2.92% | 2.43% | 0.9125 | F:51% C:32% R33:0% RAI:17% | F:52% C:32% R33:0% RAI:16% | 12.0 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:95% C:0% R21:5% RAI:1% | F:94% C:4% R:2% | 4.57% | 2.41% | 0.7267 | F:56% C:26% R35:0% RAI:18% | F:59% C:28% R35:0% RAI:13% | 11.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:94% C:0% R20:5% RAI:0% | F:93% C:5% R:2% | 5.18% | 2.43% | 0.6846 | F:52% C:30% R33:0% RAI:18% | F:56% C:32% R33:0% RAI:12% | 12.0 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% C:0% R20:2% RAI:1% | F:93% C:5% R:2% | 1.97% | 2.43% | 1.1115 | F:44% C:29% R40:0% RAI:27% | F:42% C:27% R40:0% RAI:31% | 12.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:95% C:0% R13.1:5% RAI:0% | F:93% C:4% R:2% | 4.57% | 2.28% | 0.7073 | F:39% C:37% R33:6% RAI:18% | F:43% C:40% R33:4% RAI:13% | 11.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R17.5:3% RAI:1% | F:94% C:4% R:2% | 2.68% | 2.41% | 0.9484 | F:53% C:30% R34:0% RAI:17% | F:53% C:31% R34:0% RAI:16% | 11.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R17.5:3% RAI:1% | F:93% C:5% R:2% | 2.92% | 2.43% | 0.9125 | F:52% C:30% R34:0% RAI:18% | F:53% C:30% R34:0% RAI:16% | 12.0 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:95% C:0% R21:5% RAI:1% | F:94% C:4% R:2% | 4.57% | 2.41% | 0.7267 | F:57% C:26% R35:0% RAI:17% | F:60% C:28% R35:0% RAI:12% | 11.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:94% C:0% R20:5% RAI:0% | F:93% C:5% R:2% | 5.18% | 2.43% | 0.6846 | F:52% C:32% R33:0% RAI:16% | F:55% C:34% R33:0% RAI:11% | 12.5 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% C:0% R20:2% RAI:1% | F:93% C:5% R:2% | 1.97% | 2.43% | 1.1115 | F:40% C:34% R38:1% RAI:25% | F:39% C:33% R38:1% RAI:28% | 12.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:95% C:0% R21:5% RAI:1% | F:94% C:4% R:2% | 4.57% | 2.41% | 0.7267 | F:56% C:26% R40:0% RAI:17% | F:60% C:28% R40:0% RAI:12% | 12.2 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:94% C:0% R20:5% RAI:0% | F:93% C:5% R:2% | 5.18% | 2.43% | 0.6846 | F:57% C:23% R40:0% RAI:20% | F:61% C:25% R40:0% RAI:14% | 12.1 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% C:0% R20:2% RAI:1% | F:93% C:5% R:2% | 1.97% | 2.43% | 1.1115 | F:52% C:18% R45:0% RAI:30% | F:49% C:17% R45:0% RAI:33% | 12.7 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% C:0% R20:2% RAI:1% | F:93% C:5% R:2% | 1.97% | 2.43% | 1.1115 | F:36% C:37% R40:0% RAI:27% | F:34% C:36% R40:0% RAI:30% | 12.8 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R14:4% RAI:0% | F:86% C:11% R:2% | 3.53% | 2.34% | 0.8140 | F:42% C:32% R35:5% RAI:20% | F:45% C:34% R35:4% RAI:17% | 214.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R14:4% RAI:0% | F:82% C:10% R:8% | 3.61% | 7.97% | 1.4860 | F:41% C:33% R35:6% RAI:20% | F:34% C:27% R35:9% RAI:30% | 217.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R20:3% RAI:0% | F:91% C:5% R:3% | 2.78% | 3.39% | 1.1043 | F:53% C:29% R33:0% RAI:18% | F:51% C:29% R33:0% RAI:20% | 214.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R19:3% RAI:0% | F:86% C:10% R:4% | 2.93% | 4.41% | 1.2272 | F:51% C:31% R33:0% RAI:18% | F:48% C:29% R33:0% RAI:22% | 214.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:95% C:0% R13.1:5% RAI:0% | F:82% C:10% R:8% | 4.57% | 7.97% | 1.3214 | F:41% C:34% R35:7% RAI:19% | F:36% C:30% R35:9% RAI:25% | 214.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R17.5:3% RAI:1% | F:91% C:5% R:3% | 2.68% | 3.39% | 1.1246 | F:52% C:31% R33:0% RAI:17% | F:51% C:30% R33:0% RAI:19% | 215.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R17.5:3% RAI:1% | F:86% C:10% R:4% | 2.92% | 4.41% | 1.2301 | F:51% C:32% R33:0% RAI:17% | F:48% C:30% R33:0% RAI:21% | 215.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:95% C:0% R21:5% RAI:1% | F:91% C:5% R:3% | 4.57% | 3.39% | 0.8617 | F:56% C:26% R35:0% RAI:18% | F:58% C:27% R35:0% RAI:15% | 217.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:94% C:0% R20:5% RAI:0% | F:86% C:10% R:4% | 5.18% | 4.41% | 0.9228 | F:52% C:30% R33:0% RAI:18% | F:53% C:30% R33:0% RAI:17% | 216.4 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% C:0% R20:2% RAI:1% | F:86% C:10% R:4% | 1.97% | 4.41% | 1.4984 | F:44% C:29% R40:0% RAI:27% | F:35% C:23% R40:0% RAI:41% | 218.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:95% C:0% R13.1:5% RAI:0% | F:82% C:10% R:8% | 4.57% | 7.97% | 1.3214 | F:39% C:37% R33:6% RAI:18% | F:35% C:33% R33:8% RAI:24% | 215.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R17.5:3% RAI:1% | F:91% C:5% R:3% | 2.68% | 3.39% | 1.1246 | F:53% C:30% R34:0% RAI:17% | F:52% C:30% R34:0% RAI:19% | 214.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R17.5:3% RAI:1% | F:86% C:10% R:4% | 2.92% | 4.41% | 1.2301 | F:52% C:30% R34:0% RAI:18% | F:50% C:28% R34:0% RAI:22% | 215.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:95% C:0% R21:5% RAI:1% | F:91% C:5% R:3% | 4.57% | 3.39% | 0.8617 | F:57% C:26% R35:0% RAI:17% | F:58% C:27% R35:0% RAI:14% | 215.8 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:94% C:0% R20:5% RAI:0% | F:86% C:10% R:4% | 5.18% | 4.41% | 0.9228 | F:52% C:32% R33:0% RAI:16% | F:53% C:33% R33:0% RAI:15% | 222.1 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% C:0% R20:2% RAI:1% | F:86% C:10% R:4% | 1.97% | 4.41% | 1.4984 | F:40% C:34% R38:1% RAI:25% | F:33% C:28% R38:1% RAI:38% | 214.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:95% C:0% R21:5% RAI:1% | F:91% C:5% R:3% | 4.57% | 3.39% | 0.8617 | F:56% C:26% R40:0% RAI:17% | F:58% C:27% R40:0% RAI:15% | 213.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:94% C:0% R20:5% RAI:0% | F:86% C:10% R:4% | 5.18% | 4.41% | 0.9228 | F:57% C:23% R40:0% RAI:20% | F:58% C:24% R40:0% RAI:19% | 217.3 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% C:0% R20:2% RAI:1% | F:86% C:10% R:4% | 1.97% | 4.41% | 1.4984 | F:52% C:18% R45:0% RAI:30% | F:41% C:14% R45:0% RAI:45% | 216.5 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% C:0% R20:2% RAI:1% | F:86% C:10% R:4% | 1.97% | 4.41% | 1.4984 | F:36% C:37% R40:0% RAI:27% | F:29% C:31% R40:0% RAI:40% | 219.3 |

## 数据中等 (50-300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R14:4% RAI:0% | F:33% C:33% R:33% | 3.53% | 33.33% | 3.0712 | F:42% C:32% R35:5% RAI:20% | F:12% C:9% R35:16% RAI:62% | 371.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R14:4% RAI:0% | F:33% C:33% R:33% | 3.61% | 33.33% | 3.0388 | F:41% C:33% R35:6% RAI:20% | F:12% C:9% R35:18% RAI:61% | 371.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R20:3% RAI:0% | F:33% C:33% R:33% | 2.78% | 33.33% | 3.4615 | F:53% C:29% R33:0% RAI:18% | F:24% C:13% R33:1% RAI:63% | 375.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R19:3% RAI:0% | F:50% C:25% R:25% | 2.93% | 25.00% | 2.9206 | F:51% C:31% R33:0% RAI:18% | F:29% C:18% R33:0% RAI:53% | 375.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:95% C:0% R13.1:5% RAI:0% | F:33% C:33% R:33% | 4.57% | 33.33% | 2.7021 | F:41% C:34% R35:7% RAI:19% | F:17% C:15% R35:18% RAI:50% | 375.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R17.5:3% RAI:1% | F:33% C:33% R:33% | 2.68% | 33.33% | 3.5251 | F:52% C:31% R33:0% RAI:17% | F:25% C:15% R33:0% RAI:60% | 377.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R17.5:3% RAI:1% | F:50% C:25% R:25% | 2.92% | 25.00% | 2.9277 | F:51% C:32% R33:0% RAI:17% | F:30% C:19% R33:0% RAI:51% | 381.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:95% C:0% R21:5% RAI:1% | F:33% C:33% R:33% | 4.57% | 33.33% | 2.7010 | F:56% C:26% R35:0% RAI:18% | F:35% C:16% R35:1% RAI:48% | 375.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:94% C:0% R20:5% RAI:0% | F:50% C:25% R:25% | 5.18% | 25.00% | 2.1963 | F:52% C:30% R33:0% RAI:18% | F:38% C:22% R33:0% RAI:40% | 372.7 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% C:0% R20:2% RAI:1% | F:50% C:25% R:25% | 1.97% | 25.00% | 3.5661 | F:44% C:29% R40:0% RAI:27% | F:1% C:0% R40:1% RAI:98% | 373.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:95% C:0% R13.1:5% RAI:0% | F:33% C:33% R:33% | 4.57% | 33.33% | 2.7021 | F:39% C:37% R33:6% RAI:18% | F:18% C:17% R33:16% RAI:49% | 372.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R17.5:3% RAI:1% | F:33% C:33% R:33% | 2.68% | 33.33% | 3.5251 | F:53% C:30% R34:0% RAI:17% | F:26% C:15% R34:0% RAI:59% | 377.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R17.5:3% RAI:1% | F:50% C:25% R:25% | 2.92% | 25.00% | 2.9277 | F:52% C:30% R34:0% RAI:18% | F:30% C:17% R34:0% RAI:53% | 373.7 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:95% C:0% R21:5% RAI:1% | F:33% C:33% R:33% | 4.57% | 33.33% | 2.7010 | F:57% C:26% R35:0% RAI:17% | F:37% C:17% R35:0% RAI:45% | 376.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:94% C:0% R20:5% RAI:0% | F:50% C:25% R:25% | 5.18% | 25.00% | 2.1963 | F:52% C:32% R33:0% RAI:16% | F:40% C:25% R33:0% RAI:35% | 378.5 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% C:0% R20:2% RAI:1% | F:50% C:25% R:25% | 1.97% | 25.00% | 3.5661 | F:40% C:34% R38:1% RAI:25% | F:4% C:3% R38:2% RAI:90% | 375.1 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:95% C:0% R21:5% RAI:1% | F:33% C:33% R:33% | 4.57% | 33.33% | 2.7010 | F:56% C:26% R40:0% RAI:17% | F:37% C:17% R40:0% RAI:46% | 897.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:94% C:0% R20:5% RAI:0% | F:50% C:25% R:25% | 5.18% | 25.00% | 2.1963 | F:57% C:23% R40:0% RAI:20% | F:40% C:16% R40:0% RAI:44% | 374.6 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% C:0% R20:2% RAI:1% | F:50% C:25% R:25% | 1.97% | 25.00% | 3.5661 | F:52% C:18% R45:0% RAI:30% | F:52% C:18% R45:0% RAI:30% | 366.0 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% C:0% R20:2% RAI:1% | F:50% C:25% R:25% | 1.97% | 25.00% | 3.5661 | F:36% C:37% R40:0% RAI:27% | F:2% C:2% R40:0% RAI:95% | 371.4 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R14:4% RAI:0% | F:94% C:3% R:4% | 3.53% | 3.65% | 1.0166 | F:42% C:32% R35:5% RAI:20% | F:42% C:32% R35:5% RAI:21% | 468.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R14:4% RAI:0% | F:92% C:3% R:5% | 3.61% | 5.36% | 1.2180 | F:41% C:33% R35:6% RAI:20% | F:38% C:30% R35:7% RAI:24% | 469.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R20:3% RAI:0% | F:92% C:3% R:5% | 2.78% | 5.11% | 1.3558 | F:53% C:29% R33:0% RAI:18% | F:48% C:27% R33:0% RAI:25% | 469.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R19:3% RAI:0% | F:92% C:4% R:4% | 2.93% | 4.49% | 1.2383 | F:51% C:31% R33:0% RAI:18% | F:48% C:29% R33:0% RAI:22% | 471.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:95% C:0% R13.1:5% RAI:0% | F:92% C:3% R:5% | 4.57% | 5.36% | 1.0831 | F:41% C:34% R35:7% RAI:19% | F:40% C:33% R35:7% RAI:20% | 470.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R17.5:3% RAI:1% | F:92% C:3% R:5% | 2.68% | 5.11% | 1.3807 | F:52% C:31% R33:0% RAI:17% | F:48% C:28% R33:0% RAI:23% | 468.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R17.5:3% RAI:1% | F:92% C:4% R:4% | 2.92% | 4.49% | 1.2413 | F:51% C:32% R33:0% RAI:17% | F:48% C:30% R33:0% RAI:21% | 471.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:95% C:0% R21:5% RAI:1% | F:92% C:3% R:5% | 4.57% | 5.11% | 1.0579 | F:56% C:26% R35:0% RAI:18% | F:55% C:26% R35:0% RAI:19% | 474.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:94% C:0% R20:5% RAI:0% | F:92% C:4% R:4% | 5.18% | 4.49% | 0.9312 | F:52% C:30% R33:0% RAI:18% | F:53% C:30% R33:0% RAI:17% | 465.3 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% C:0% R20:2% RAI:1% | F:92% C:4% R:4% | 1.97% | 4.49% | 1.5120 | F:44% C:29% R40:0% RAI:27% | F:35% C:23% R40:0% RAI:42% | 466.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:95% C:0% R13.1:5% RAI:0% | F:92% C:3% R:5% | 4.57% | 5.36% | 1.0831 | F:39% C:37% R33:6% RAI:18% | F:38% C:36% R33:7% RAI:20% | 470.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R17.5:3% RAI:1% | F:92% C:3% R:5% | 2.68% | 5.11% | 1.3807 | F:53% C:30% R34:0% RAI:17% | F:49% C:28% R34:0% RAI:23% | 468.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R17.5:3% RAI:1% | F:92% C:4% R:4% | 2.92% | 4.49% | 1.2413 | F:52% C:30% R34:0% RAI:18% | F:49% C:28% R34:0% RAI:22% | 463.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:95% C:0% R21:5% RAI:1% | F:92% C:3% R:5% | 4.57% | 5.11% | 1.0579 | F:57% C:26% R35:0% RAI:17% | F:56% C:26% R35:0% RAI:18% | 469.5 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:94% C:0% R20:5% RAI:0% | F:92% C:4% R:4% | 5.18% | 4.49% | 0.9312 | F:52% C:32% R33:0% RAI:16% | F:52% C:33% R33:0% RAI:15% | 468.3 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% C:0% R20:2% RAI:1% | F:92% C:4% R:4% | 1.97% | 4.49% | 1.5120 | F:40% C:34% R38:1% RAI:25% | F:33% C:28% R38:1% RAI:38% | 467.9 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:95% C:0% R21:5% RAI:1% | F:92% C:3% R:5% | 4.57% | 5.11% | 1.0579 | F:56% C:26% R40:0% RAI:17% | F:56% C:26% R40:0% RAI:18% | 471.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:94% C:0% R20:5% RAI:0% | F:92% C:4% R:4% | 5.18% | 4.49% | 0.9312 | F:57% C:23% R40:0% RAI:20% | F:58% C:24% R40:0% RAI:19% | 467.6 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% C:0% R20:2% RAI:1% | F:92% C:4% R:4% | 1.97% | 4.49% | 1.5120 | F:52% C:18% R45:0% RAI:30% | F:40% C:14% R45:0% RAI:46% | 466.9 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% C:0% R20:2% RAI:1% | F:92% C:4% R:4% | 1.97% | 4.49% | 1.5120 | F:36% C:37% R40:0% RAI:27% | F:29% C:30% R40:0% RAI:40% | 468.5 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R14:4% RAI:0% | F:88% C:2% R:9% | 3.53% | 9.31% | 1.6227 | F:42% C:32% R35:5% RAI:20% | F:33% C:25% R35:8% RAI:33% | 396.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R14:4% RAI:0% | F:89% C:8% R:2% | 3.61% | 2.34% | 0.8055 | F:41% C:33% R35:6% RAI:20% | F:44% C:35% R35:5% RAI:16% | 394.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R20:3% RAI:0% | F:80% C:11% R:9% | 2.78% | 9.34% | 1.8323 | F:53% C:29% R33:0% RAI:18% | F:43% C:24% R33:0% RAI:33% | 390.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R19:3% RAI:0% | F:90% C:7% R:3% | 2.93% | 2.88% | 0.9910 | F:51% C:31% R33:0% RAI:18% | F:51% C:31% R33:0% RAI:18% | 395.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:95% C:0% R13.1:5% RAI:0% | F:89% C:8% R:2% | 4.57% | 2.34% | 0.7162 | F:41% C:34% R35:7% RAI:19% | F:45% C:37% R35:5% RAI:13% | 398.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R17.5:3% RAI:1% | F:80% C:11% R:9% | 2.68% | 9.34% | 1.8659 | F:52% C:31% R33:0% RAI:17% | F:43% C:25% R33:0% RAI:32% | 391.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R17.5:3% RAI:1% | F:90% C:7% R:3% | 2.92% | 2.88% | 0.9934 | F:51% C:32% R33:0% RAI:17% | F:51% C:32% R33:0% RAI:17% | 395.7 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:95% C:0% R21:5% RAI:1% | F:80% C:11% R:9% | 4.57% | 9.34% | 1.4297 | F:56% C:26% R35:0% RAI:18% | F:51% C:24% R35:0% RAI:25% | 399.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:94% C:0% R20:5% RAI:0% | F:90% C:7% R:3% | 5.18% | 2.88% | 0.7452 | F:52% C:30% R33:0% RAI:18% | F:55% C:31% R33:0% RAI:14% | 395.0 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% C:0% R20:2% RAI:1% | F:90% C:7% R:3% | 1.97% | 2.88% | 1.2100 | F:44% C:29% R40:0% RAI:27% | F:40% C:26% R40:0% RAI:33% | 395.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:95% C:0% R13.1:5% RAI:0% | F:89% C:8% R:2% | 4.57% | 2.34% | 0.7162 | F:39% C:37% R33:6% RAI:18% | F:43% C:40% R33:4% RAI:13% | 393.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R17.5:3% RAI:1% | F:80% C:11% R:9% | 2.68% | 9.34% | 1.8659 | F:53% C:30% R34:0% RAI:17% | F:44% C:25% R34:0% RAI:31% | 392.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R17.5:3% RAI:1% | F:90% C:7% R:3% | 2.92% | 2.88% | 0.9934 | F:52% C:30% R34:0% RAI:18% | F:52% C:30% R34:0% RAI:18% | 393.8 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:95% C:0% R21:5% RAI:1% | F:80% C:11% R:9% | 4.57% | 9.34% | 1.4297 | F:57% C:26% R35:0% RAI:17% | F:52% C:24% R35:0% RAI:24% | 394.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:94% C:0% R20:5% RAI:0% | F:90% C:7% R:3% | 5.18% | 2.88% | 0.7452 | F:52% C:32% R33:0% RAI:16% | F:54% C:34% R33:0% RAI:12% | 392.6 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% C:0% R20:2% RAI:1% | F:90% C:7% R:3% | 1.97% | 2.88% | 1.2100 | F:40% C:34% R38:1% RAI:25% | F:37% C:31% R38:1% RAI:31% | 392.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:95% C:0% R21:5% RAI:1% | F:80% C:11% R:9% | 4.57% | 9.34% | 1.4297 | F:56% C:26% R40:0% RAI:17% | F:51% C:24% R40:0% RAI:24% | 391.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:94% C:0% R20:5% RAI:0% | F:90% C:7% R:3% | 5.18% | 2.88% | 0.7452 | F:57% C:23% R40:0% RAI:20% | F:60% C:25% R40:0% RAI:15% | 390.6 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% C:0% R20:2% RAI:1% | F:90% C:7% R:3% | 1.97% | 2.88% | 1.2100 | F:52% C:18% R45:0% RAI:30% | F:47% C:16% R45:0% RAI:36% | 396.4 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% C:0% R20:2% RAI:1% | F:90% C:7% R:3% | 1.97% | 2.88% | 1.2100 | F:36% C:37% R40:0% RAI:27% | F:33% C:35% R40:0% RAI:32% | 394.3 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R14:4% RAI:0% | F:81% C:10% R:10% | 3.53% | 9.71% | 1.6575 | F:42% C:32% R35:5% RAI:20% | F:33% C:25% R35:9% RAI:34% | 441.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R14:4% RAI:0% | F:86% C:9% R:5% | 3.61% | 5.22% | 1.2022 | F:41% C:33% R35:6% RAI:20% | F:38% C:31% R35:7% RAI:24% | 437.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R20:3% RAI:0% | F:79% C:15% R:5% | 2.78% | 5.36% | 1.3883 | F:53% C:29% R33:0% RAI:18% | F:48% C:27% R33:0% RAI:25% | 440.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R19:3% RAI:0% | F:83% C:13% R:3% | 2.93% | 3.23% | 1.0503 | F:51% C:31% R33:0% RAI:18% | F:50% C:31% R33:0% RAI:19% | 441.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:95% C:0% R13.1:5% RAI:0% | F:86% C:9% R:5% | 4.57% | 5.22% | 1.0690 | F:41% C:34% R35:7% RAI:19% | F:40% C:33% R35:7% RAI:20% | 440.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R17.5:3% RAI:1% | F:79% C:15% R:5% | 2.68% | 5.36% | 1.4138 | F:52% C:31% R33:0% RAI:17% | F:48% C:28% R33:0% RAI:24% | 440.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R17.5:3% RAI:1% | F:83% C:13% R:3% | 2.92% | 3.23% | 1.0528 | F:51% C:32% R33:0% RAI:17% | F:50% C:31% R33:0% RAI:18% | 443.3 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:95% C:0% R21:5% RAI:1% | F:79% C:15% R:5% | 4.57% | 5.36% | 1.0833 | F:56% C:26% R35:0% RAI:18% | F:55% C:26% R35:0% RAI:19% | 441.2 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:94% C:0% R20:5% RAI:0% | F:83% C:13% R:3% | 5.18% | 3.23% | 0.7898 | F:52% C:30% R33:0% RAI:18% | F:54% C:31% R33:0% RAI:14% | 444.2 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% C:0% R20:2% RAI:1% | F:83% C:13% R:3% | 1.97% | 3.23% | 1.2824 | F:44% C:29% R40:0% RAI:27% | F:39% C:26% R40:0% RAI:35% | 442.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:95% C:0% R13.1:5% RAI:0% | F:86% C:9% R:5% | 4.57% | 5.22% | 1.0690 | F:39% C:37% R33:6% RAI:18% | F:38% C:36% R33:7% RAI:19% | 439.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R17.5:3% RAI:1% | F:79% C:15% R:5% | 2.68% | 5.36% | 1.4138 | F:53% C:30% R34:0% RAI:17% | F:48% C:28% R34:0% RAI:24% | 443.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R17.5:3% RAI:1% | F:83% C:13% R:3% | 2.92% | 3.23% | 1.0528 | F:52% C:30% R34:0% RAI:18% | F:52% C:29% R34:0% RAI:19% | 443.7 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:95% C:0% R21:5% RAI:1% | F:79% C:15% R:5% | 4.57% | 5.36% | 1.0833 | F:57% C:26% R35:0% RAI:17% | F:56% C:26% R35:0% RAI:18% | 439.7 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:94% C:0% R20:5% RAI:0% | F:83% C:13% R:3% | 5.18% | 3.23% | 0.7898 | F:52% C:32% R33:0% RAI:16% | F:54% C:34% R33:0% RAI:13% | 444.5 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% C:0% R20:2% RAI:1% | F:83% C:13% R:3% | 1.97% | 3.23% | 1.2824 | F:40% C:34% R38:1% RAI:25% | F:36% C:31% R38:1% RAI:33% | 439.1 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:95% C:0% R21:5% RAI:1% | F:79% C:15% R:5% | 4.57% | 5.36% | 1.0833 | F:56% C:26% R40:0% RAI:17% | F:55% C:26% R40:0% RAI:19% | 437.2 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:94% C:0% R20:5% RAI:0% | F:83% C:13% R:3% | 5.18% | 3.23% | 0.7898 | F:57% C:23% R40:0% RAI:20% | F:60% C:24% R40:0% RAI:16% | 440.2 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% C:0% R20:2% RAI:1% | F:83% C:13% R:3% | 1.97% | 3.23% | 1.2824 | F:52% C:18% R45:0% RAI:30% | F:45% C:16% R45:0% RAI:39% | 441.5 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% C:0% R20:2% RAI:1% | F:83% C:13% R:3% | 1.97% | 3.23% | 1.2824 | F:36% C:37% R40:0% RAI:27% | F:32% C:34% R40:0% RAI:34% | 442.8 |

## 数据充足 (>300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R14:4% RAI:0% | F:88% C:2% R:10% | 3.53% | 9.76% | 1.6618 | F:42% C:32% R35:5% RAI:20% | F:33% C:25% R35:9% RAI:34% | 452.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R14:4% RAI:0% | F:92% C:6% R:2% | 3.61% | 2.25% | 0.7896 | F:41% C:33% R35:6% RAI:20% | F:44% C:35% R35:5% RAI:16% | 460.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R20:3% RAI:0% | F:93% C:5% R:2% | 2.78% | 2.25% | 0.8996 | F:53% C:29% R33:0% RAI:18% | F:54% C:30% R33:0% RAI:16% | 456.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R19:3% RAI:0% | F:94% C:4% R:2% | 2.93% | 2.09% | 0.8436 | F:51% C:31% R33:0% RAI:18% | F:53% C:32% R33:0% RAI:15% | 457.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:95% C:0% R13.1:5% RAI:0% | F:92% C:6% R:2% | 4.57% | 2.25% | 0.7022 | F:41% C:34% R35:7% RAI:19% | F:45% C:37% R35:5% RAI:13% | 455.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R17.5:3% RAI:1% | F:93% C:5% R:2% | 2.68% | 2.25% | 0.9161 | F:52% C:31% R33:0% RAI:17% | F:53% C:31% R33:0% RAI:15% | 457.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R17.5:3% RAI:1% | F:94% C:4% R:2% | 2.92% | 2.09% | 0.8456 | F:51% C:32% R33:0% RAI:17% | F:52% C:33% R33:0% RAI:15% | 461.5 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:95% C:0% R21:5% RAI:1% | F:93% C:5% R:2% | 4.57% | 2.25% | 0.7019 | F:56% C:26% R35:0% RAI:18% | F:60% C:28% R35:0% RAI:12% | 461.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:94% C:0% R20:5% RAI:0% | F:94% C:4% R:2% | 5.18% | 2.09% | 0.6344 | F:52% C:30% R33:0% RAI:18% | F:56% C:32% R33:0% RAI:12% | 452.3 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% C:0% R20:2% RAI:1% | F:94% C:4% R:2% | 1.97% | 2.09% | 1.0300 | F:44% C:29% R40:0% RAI:27% | F:43% C:28% R40:0% RAI:28% | 454.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:95% C:0% R13.1:5% RAI:0% | F:92% C:6% R:2% | 4.57% | 2.25% | 0.7022 | F:39% C:37% R33:6% RAI:18% | F:43% C:40% R33:4% RAI:13% | 457.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R17.5:3% RAI:1% | F:93% C:5% R:2% | 2.68% | 2.25% | 0.9161 | F:53% C:30% R34:0% RAI:17% | F:54% C:31% R34:0% RAI:15% | 456.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R17.5:3% RAI:1% | F:94% C:4% R:2% | 2.92% | 2.09% | 0.8456 | F:52% C:30% R34:0% RAI:18% | F:54% C:31% R34:0% RAI:15% | 455.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:95% C:0% R21:5% RAI:1% | F:93% C:5% R:2% | 4.57% | 2.25% | 0.7019 | F:57% C:26% R35:0% RAI:17% | F:60% C:28% R35:0% RAI:12% | 468.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:94% C:0% R20:5% RAI:0% | F:94% C:4% R:2% | 5.18% | 2.09% | 0.6344 | F:52% C:32% R33:0% RAI:16% | F:55% C:34% R33:0% RAI:10% | 453.5 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% C:0% R20:2% RAI:1% | F:94% C:4% R:2% | 1.97% | 2.09% | 1.0300 | F:40% C:34% R38:1% RAI:25% | F:40% C:34% R38:1% RAI:26% | 459.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:95% C:0% R21:5% RAI:1% | F:93% C:5% R:2% | 4.57% | 2.25% | 0.7019 | F:56% C:26% R40:0% RAI:17% | F:60% C:28% R40:0% RAI:12% | 455.9 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:94% C:0% R20:5% RAI:0% | F:94% C:4% R:2% | 5.18% | 2.09% | 0.6344 | F:57% C:23% R40:0% RAI:20% | F:62% C:25% R40:0% RAI:13% | 452.9 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% C:0% R20:2% RAI:1% | F:94% C:4% R:2% | 1.97% | 2.09% | 1.0300 | F:52% C:18% R45:0% RAI:30% | F:51% C:18% R45:0% RAI:31% | 452.7 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% C:0% R20:2% RAI:1% | F:94% C:4% R:2% | 1.97% | 2.09% | 1.0300 | F:36% C:37% R40:0% RAI:27% | F:35% C:37% R40:0% RAI:27% | 456.5 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R14:4% RAI:0% | F:90% C:7% R:3% | 3.53% | 3.09% | 0.9347 | F:42% C:32% R35:5% RAI:20% | F:43% C:33% R35:5% RAI:19% | 420.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R14:4% RAI:0% | F:87% C:10% R:3% | 3.61% | 2.97% | 0.9070 | F:41% C:33% R35:6% RAI:20% | F:43% C:34% R35:5% RAI:18% | 419.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R20:3% RAI:0% | F:88% C:10% R:2% | 2.78% | 2.34% | 0.9176 | F:53% C:29% R33:0% RAI:18% | F:54% C:30% R33:0% RAI:17% | 424.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R19:3% RAI:0% | F:88% C:8% R:4% | 2.93% | 3.73% | 1.1285 | F:51% C:31% R33:0% RAI:18% | F:49% C:30% R33:0% RAI:20% | 432.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:95% C:0% R13.1:5% RAI:0% | F:87% C:10% R:3% | 4.57% | 2.97% | 0.8066 | F:41% C:34% R35:7% RAI:19% | F:43% C:36% R35:5% RAI:15% | 422.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R17.5:3% RAI:1% | F:88% C:10% R:2% | 2.68% | 2.34% | 0.9344 | F:52% C:31% R33:0% RAI:17% | F:53% C:31% R33:0% RAI:16% | 424.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R17.5:3% RAI:1% | F:88% C:8% R:4% | 2.92% | 3.73% | 1.1312 | F:51% C:32% R33:0% RAI:17% | F:49% C:31% R33:0% RAI:20% | 428.0 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:95% C:0% R21:5% RAI:1% | F:88% C:10% R:2% | 4.57% | 2.34% | 0.7160 | F:56% C:26% R35:0% RAI:18% | F:59% C:28% R35:0% RAI:13% | 423.0 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:94% C:0% R20:5% RAI:0% | F:88% C:8% R:4% | 5.18% | 3.73% | 0.8486 | F:52% C:30% R33:0% RAI:18% | F:54% C:31% R33:0% RAI:15% | 427.1 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% C:0% R20:2% RAI:1% | F:88% C:8% R:4% | 1.97% | 3.73% | 1.3778 | F:44% C:29% R40:0% RAI:27% | F:37% C:25% R40:0% RAI:38% | 425.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:95% C:0% R13.1:5% RAI:0% | F:87% C:10% R:3% | 4.57% | 2.97% | 0.8066 | F:39% C:37% R33:6% RAI:18% | F:42% C:39% R33:5% RAI:15% | 428.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R17.5:3% RAI:1% | F:88% C:10% R:2% | 2.68% | 2.34% | 0.9344 | F:53% C:30% R34:0% RAI:17% | F:54% C:31% R34:0% RAI:16% | 425.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R17.5:3% RAI:1% | F:88% C:8% R:4% | 2.92% | 3.73% | 1.1312 | F:52% C:30% R34:0% RAI:18% | F:51% C:29% R34:0% RAI:20% | 427.8 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:95% C:0% R21:5% RAI:1% | F:88% C:10% R:2% | 4.57% | 2.34% | 0.7160 | F:57% C:26% R35:0% RAI:17% | F:60% C:28% R35:0% RAI:12% | 422.5 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:94% C:0% R20:5% RAI:0% | F:88% C:8% R:4% | 5.18% | 3.73% | 0.8486 | F:52% C:32% R33:0% RAI:16% | F:53% C:33% R33:0% RAI:14% | 417.7 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% C:0% R20:2% RAI:1% | F:88% C:8% R:4% | 1.97% | 3.73% | 1.3778 | F:40% C:34% R38:1% RAI:25% | F:35% C:29% R38:1% RAI:35% | 425.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:95% C:0% R21:5% RAI:1% | F:88% C:10% R:2% | 4.57% | 2.34% | 0.7160 | F:56% C:26% R40:0% RAI:17% | F:60% C:28% R40:0% RAI:12% | 420.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:94% C:0% R20:5% RAI:0% | F:88% C:8% R:4% | 5.18% | 3.73% | 0.8486 | F:57% C:23% R40:0% RAI:20% | F:59% C:24% R40:0% RAI:17% | 418.4 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% C:0% R20:2% RAI:1% | F:88% C:8% R:4% | 1.97% | 3.73% | 1.3778 | F:52% C:18% R45:0% RAI:30% | F:43% C:15% R45:0% RAI:42% | 424.1 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% C:0% R20:2% RAI:1% | F:88% C:8% R:4% | 1.97% | 3.73% | 1.3778 | F:36% C:37% R40:0% RAI:27% | F:31% C:32% R40:0% RAI:37% | 422.0 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R14:4% RAI:0% | F:78% C:11% R:11% | 3.53% | 11.04% | 1.7677 | F:42% C:32% R35:5% RAI:20% | F:31% C:24% R35:9% RAI:36% | 379.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R14:4% RAI:0% | F:86% C:7% R:7% | 3.61% | 6.88% | 1.3805 | F:41% C:33% R35:6% RAI:20% | F:36% C:28% R35:8% RAI:28% | 892.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R20:3% RAI:0% | F:79% C:14% R:7% | 2.78% | 7.08% | 1.5954 | F:53% C:29% R33:0% RAI:18% | F:46% C:25% R33:0% RAI:29% | 371.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R19:3% RAI:0% | F:85% C:13% R:3% | 2.93% | 2.51% | 0.9259 | F:51% C:31% R33:0% RAI:18% | F:52% C:32% R33:0% RAI:17% | 376.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:95% C:0% R13.1:5% RAI:0% | F:86% C:7% R:7% | 4.57% | 6.88% | 1.2276 | F:41% C:34% R35:7% RAI:19% | F:38% C:31% R35:8% RAI:23% | 370.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R17.5:3% RAI:1% | F:79% C:14% R:7% | 2.68% | 7.08% | 1.6247 | F:52% C:31% R33:0% RAI:17% | F:46% C:27% R33:0% RAI:27% | 375.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R17.5:3% RAI:1% | F:85% C:13% R:3% | 2.92% | 2.51% | 0.9281 | F:51% C:32% R33:0% RAI:17% | F:51% C:32% R33:0% RAI:16% | 906.0 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:95% C:0% R21:5% RAI:1% | F:79% C:14% R:7% | 4.57% | 7.08% | 1.2449 | F:56% C:26% R35:0% RAI:18% | F:53% C:25% R35:0% RAI:22% | 369.7 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:94% C:0% R20:5% RAI:0% | F:85% C:13% R:3% | 5.18% | 2.51% | 0.6962 | F:52% C:30% R33:0% RAI:18% | F:56% C:32% R33:0% RAI:13% | 369.0 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% C:0% R20:2% RAI:1% | F:85% C:13% R:3% | 1.97% | 2.51% | 1.1305 | F:44% C:29% R40:0% RAI:27% | F:41% C:27% R40:0% RAI:31% | 371.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:95% C:0% R13.1:5% RAI:0% | F:86% C:7% R:7% | 4.57% | 6.88% | 1.2276 | F:39% C:37% R33:6% RAI:18% | F:36% C:34% R33:7% RAI:22% | 368.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R17.5:3% RAI:1% | F:79% C:14% R:7% | 2.68% | 7.08% | 1.6247 | F:53% C:30% R34:0% RAI:17% | F:46% C:26% R34:0% RAI:27% | 367.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R17.5:3% RAI:1% | F:85% C:13% R:3% | 2.92% | 2.51% | 0.9281 | F:52% C:30% R34:0% RAI:18% | F:53% C:30% R34:0% RAI:17% | 369.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:95% C:0% R21:5% RAI:1% | F:79% C:14% R:7% | 4.57% | 7.08% | 1.2449 | F:57% C:26% R35:0% RAI:17% | F:54% C:25% R35:0% RAI:21% | 371.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:94% C:0% R20:5% RAI:0% | F:85% C:13% R:3% | 5.18% | 2.51% | 0.6962 | F:52% C:32% R33:0% RAI:16% | F:55% C:34% R33:0% RAI:11% | 368.7 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% C:0% R20:2% RAI:1% | F:85% C:13% R:3% | 1.97% | 2.51% | 1.1305 | F:40% C:34% R38:1% RAI:25% | F:38% C:32% R38:1% RAI:29% | 368.2 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:95% C:0% R21:5% RAI:1% | F:79% C:14% R:7% | 4.57% | 7.08% | 1.2449 | F:56% C:26% R40:0% RAI:17% | F:54% C:25% R40:0% RAI:21% | 371.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:94% C:0% R20:5% RAI:0% | F:85% C:13% R:3% | 5.18% | 2.51% | 0.6962 | F:57% C:23% R40:0% RAI:20% | F:61% C:25% R40:0% RAI:14% | 372.2 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% C:0% R20:2% RAI:1% | F:85% C:13% R:3% | 1.97% | 2.51% | 1.1305 | F:52% C:18% R45:0% RAI:30% | F:49% C:17% R45:0% RAI:34% | 373.4 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% C:0% R20:2% RAI:1% | F:85% C:13% R:3% | 1.97% | 2.51% | 1.1305 | F:36% C:37% R40:0% RAI:27% | F:34% C:36% R40:0% RAI:30% | 366.7 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 对手GTO先验(R/C/F) | 对手统计后验(R/C/F) | 对手Range先验 | 对手Range后验 | 激进度比 | Hero先验分布 | Hero后验分布 | 耗时(ms) |
|---------|------|------|------|-----|-------------------|-------------------|-------------|-------------|--------|------------|------------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R14:4% RAI:0% | F:86% C:3% R:11% | 3.53% | 10.97% | 1.7619 | F:42% C:32% R35:5% RAI:20% | F:31% C:24% R35:9% RAI:36% | 486.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R14:4% RAI:0% | F:93% C:3% R:4% | 3.61% | 3.66% | 1.0067 | F:41% C:33% R35:6% RAI:20% | F:41% C:33% R35:6% RAI:20% | 491.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R20:3% RAI:0% | F:85% C:5% R:10% | 2.78% | 10.00% | 1.8962 | F:53% C:29% R33:0% RAI:18% | F:42% C:23% R33:0% RAI:34% | 501.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R19:3% RAI:0% | F:92% C:4% R:4% | 2.93% | 3.70% | 1.1237 | F:51% C:31% R33:0% RAI:18% | F:49% C:30% R33:0% RAI:20% | 489.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:95% C:0% R13.1:5% RAI:0% | F:93% C:3% R:4% | 4.57% | 3.66% | 0.8951 | F:41% C:34% R35:7% RAI:19% | F:42% C:35% R35:6% RAI:17% | 493.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R17.5:3% RAI:1% | F:85% C:5% R:10% | 2.68% | 10.00% | 1.9310 | F:52% C:31% R33:0% RAI:17% | F:42% C:25% R33:0% RAI:33% | 495.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R17.5:3% RAI:1% | F:92% C:4% R:4% | 2.92% | 3.70% | 1.1264 | F:51% C:32% R33:0% RAI:17% | F:49% C:31% R33:0% RAI:19% | 494.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:95% C:0% R21:5% RAI:1% | F:85% C:5% R:10% | 4.57% | 10.00% | 1.4796 | F:56% C:26% R35:0% RAI:18% | F:50% C:23% R35:0% RAI:26% | 491.5 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:94% C:0% R20:5% RAI:0% | F:92% C:4% R:4% | 5.18% | 3.70% | 0.8450 | F:52% C:30% R33:0% RAI:18% | F:54% C:31% R33:0% RAI:15% | 493.9 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% C:0% R20:2% RAI:1% | F:92% C:4% R:4% | 1.97% | 3.70% | 1.3721 | F:44% C:29% R40:0% RAI:27% | F:37% C:25% R40:0% RAI:38% | 490.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:95% C:0% R13.1:5% RAI:0% | F:93% C:3% R:4% | 4.57% | 3.66% | 0.8951 | F:39% C:37% R33:6% RAI:18% | F:40% C:38% R33:5% RAI:16% | 495.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R17.5:3% RAI:1% | F:85% C:5% R:10% | 2.68% | 10.00% | 1.9310 | F:53% C:30% R34:0% RAI:17% | F:43% C:25% R34:0% RAI:32% | 991.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R17.5:3% RAI:1% | F:92% C:4% R:4% | 2.92% | 3.70% | 1.1264 | F:52% C:30% R34:0% RAI:18% | F:51% C:29% R34:0% RAI:20% | 488.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:95% C:0% R21:5% RAI:1% | F:85% C:5% R:10% | 4.57% | 10.00% | 1.4796 | F:57% C:26% R35:0% RAI:17% | F:51% C:24% R35:0% RAI:25% | 487.7 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:94% C:0% R20:5% RAI:0% | F:92% C:4% R:4% | 5.18% | 3.70% | 0.8450 | F:52% C:32% R33:0% RAI:16% | F:53% C:33% R33:0% RAI:13% | 497.4 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% C:0% R20:2% RAI:1% | F:92% C:4% R:4% | 1.97% | 3.70% | 1.3721 | F:40% C:34% R38:1% RAI:25% | F:35% C:29% R38:1% RAI:35% | 489.2 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:95% C:0% R21:5% RAI:1% | F:85% C:5% R:10% | 4.57% | 10.00% | 1.4796 | F:56% C:26% R40:0% RAI:17% | F:51% C:24% R40:0% RAI:25% | 490.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:94% C:0% R20:5% RAI:0% | F:92% C:4% R:4% | 5.18% | 3.70% | 0.8450 | F:57% C:23% R40:0% RAI:20% | F:59% C:24% R40:0% RAI:17% | 489.2 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% C:0% R20:2% RAI:1% | F:92% C:4% R:4% | 1.97% | 3.70% | 1.3721 | F:52% C:18% R45:0% RAI:30% | F:43% C:15% R45:0% RAI:41% | 491.5 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% C:0% R20:2% RAI:1% | F:92% C:4% R:4% | 1.97% | 3.70% | 1.3721 | F:36% C:37% R40:0% RAI:27% | F:31% C:32% R40:0% RAI:37% | 499.9 |

