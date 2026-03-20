# Hero_Open_Facing_4-Bet 场景测试报告

总耗时: 152318.3ms

## 数据不足 (<50手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | xMichax | 4 | 0.0% | 0.0% | F:88% R29:1% RAI:11% | F:92% R29:1% RAI:7% | 19.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:88% R28:1% RAI:11% | F:92% R28:1% RAI:7% | 19.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R35:0% RAI:10% | F:92% R35:0% RAI:8% | 19.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R35:0% RAI:11% | F:92% R35:0% RAI:8% | 19.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:88% R28:1% RAI:11% | F:92% R28:1% RAI:7% | 20.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R35:0% RAI:11% | F:91% R35:0% RAI:9% | 20.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R35:0% RAI:11% | F:91% R35:0% RAI:9% | 20.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R36:0% RAI:11% | F:92% R36:0% RAI:8% | 20.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R35:0% RAI:11% | F:92% R35:0% RAI:8% | 21.0 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:90% R34:0% RAI:10% | F:87% R34:0% RAI:13% | 21.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R28:2% RAI:9% | F:94% R28:1% RAI:5% | 19.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R35:0% RAI:11% | F:92% R35:0% RAI:8% | 20.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:88% R35:1% RAI:10% | F:91% R35:1% RAI:8% | 20.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R36:1% RAI:11% | F:92% R36:0% RAI:7% | 20.6 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:88% R33:1% RAI:11% | F:92% R33:1% RAI:7% | 20.8 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:89% R35:0% RAI:11% | F:88% R35:0% RAI:12% | 21.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:91% R40:0% RAI:9% | F:95% R40:0% RAI:5% | 20.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:91% R40:0% RAI:9% | F:95% R40:0% RAI:5% | 20.8 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:91% R45:0% RAI:9% | F:91% R45:0% RAI:9% | 21.2 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:92% R37:0% RAI:8% | F:93% R37:0% RAI:6% | 21.1 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | elvq | 12 | 16.7% | 16.7% | F:88% R29:1% RAI:11% | F:64% R29:3% RAI:33% | 426.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:88% R28:1% RAI:11% | F:64% R28:3% RAI:33% | 421.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:89% R35:0% RAI:10% | F:64% R35:1% RAI:35% | 420.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:89% R35:0% RAI:11% | F:65% R35:1% RAI:34% | 422.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:88% R28:1% RAI:11% | F:68% R28:3% RAI:29% | 421.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:89% R35:0% RAI:11% | F:63% R35:1% RAI:36% | 427.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:89% R35:0% RAI:11% | F:65% R35:0% RAI:35% | 422.8 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:89% R36:0% RAI:11% | F:69% R36:0% RAI:30% | 424.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:89% R35:0% RAI:11% | F:71% R35:0% RAI:29% | 883.7 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:90% R34:0% RAI:10% | F:52% R34:1% RAI:47% | 421.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:89% R28:2% RAI:9% | F:75% R28:4% RAI:21% | 423.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:89% R35:0% RAI:11% | F:67% R35:0% RAI:33% | 435.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:88% R35:1% RAI:10% | F:67% R35:4% RAI:29% | 420.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:89% R36:1% RAI:11% | F:72% R36:2% RAI:27% | 426.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:88% R33:1% RAI:11% | F:72% R33:2% RAI:26% | 425.8 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:89% R35:0% RAI:11% | F:54% R35:0% RAI:46% | 885.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:91% R40:0% RAI:9% | F:80% R40:0% RAI:20% | 426.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:91% R40:0% RAI:9% | F:81% R40:0% RAI:19% | 418.9 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:91% R45:0% RAI:9% | F:68% R45:0% RAI:32% | 420.4 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:92% R37:0% RAI:8% | F:76% R37:0% RAI:24% | 424.6 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | afclockey49 | 6 | 83.3% | 0.0% | F:88% R29:1% RAI:11% | F:92% R29:1% RAI:7% | 19.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:88% R28:1% RAI:11% | F:92% R28:1% RAI:7% | 19.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R35:0% RAI:10% | F:92% R35:0% RAI:8% | 19.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R35:0% RAI:11% | F:92% R35:0% RAI:8% | 20.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:88% R28:1% RAI:11% | F:92% R28:1% RAI:7% | 19.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R35:0% RAI:11% | F:91% R35:0% RAI:9% | 20.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R35:0% RAI:11% | F:91% R35:0% RAI:9% | 20.2 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R36:0% RAI:11% | F:92% R36:0% RAI:8% | 20.1 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R35:0% RAI:11% | F:92% R35:0% RAI:8% | 20.8 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:90% R34:0% RAI:10% | F:87% R34:0% RAI:13% | 21.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R28:2% RAI:9% | F:94% R28:1% RAI:5% | 20.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R35:0% RAI:11% | F:92% R35:0% RAI:8% | 20.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:88% R35:1% RAI:10% | F:91% R35:1% RAI:8% | 20.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R36:1% RAI:11% | F:92% R36:0% RAI:7% | 20.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:88% R33:1% RAI:11% | F:92% R33:1% RAI:7% | 21.0 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:89% R35:0% RAI:11% | F:88% R35:0% RAI:12% | 26.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:91% R40:0% RAI:9% | F:95% R40:0% RAI:5% | 20.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:91% R40:0% RAI:9% | F:95% R40:0% RAI:5% | 21.1 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:91% R45:0% RAI:9% | F:91% R45:0% RAI:9% | 21.3 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:92% R37:0% RAI:8% | F:93% R37:0% RAI:6% | 21.0 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Badforyou | 10 | 30.0% | 22.2% | F:88% R29:1% RAI:11% | F:52% R29:5% RAI:44% | 417.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:88% R28:1% RAI:11% | F:52% R28:4% RAI:44% | 416.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R35:0% RAI:10% | F:52% R35:2% RAI:46% | 413.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R35:0% RAI:11% | F:52% R35:1% RAI:46% | 419.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:88% R28:1% RAI:11% | F:57% R28:4% RAI:39% | 417.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R35:0% RAI:11% | F:50% R35:1% RAI:49% | 414.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R35:0% RAI:11% | F:51% R35:0% RAI:48% | 415.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R36:0% RAI:11% | F:59% R36:1% RAI:41% | 419.3 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R35:0% RAI:11% | F:60% R35:1% RAI:40% | 418.1 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:90% R34:0% RAI:10% | F:49% R34:1% RAI:51% | 418.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R28:2% RAI:9% | F:66% R28:5% RAI:29% | 416.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R35:0% RAI:11% | F:56% R35:0% RAI:44% | 413.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:88% R35:1% RAI:10% | F:54% R35:5% RAI:40% | 419.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R36:1% RAI:11% | F:62% R36:2% RAI:36% | 415.6 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:88% R33:1% RAI:11% | F:62% R33:3% RAI:36% | 426.7 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:89% R35:0% RAI:11% | F:46% R35:0% RAI:54% | 424.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:91% R40:0% RAI:9% | F:73% R40:0% RAI:27% | 412.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:91% R40:0% RAI:9% | F:74% R40:0% RAI:26% | 416.1 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:91% R45:0% RAI:9% | F:58% R45:0% RAI:42% | 418.5 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:92% R37:0% RAI:8% | F:68% R37:0% RAI:32% | 419.2 |

## 数据中等 (50-300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Turbem | 116 | 22.4% | 15.0% | F:88% R29:1% RAI:11% | F:68% R29:3% RAI:29% | 709.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:88% R28:1% RAI:11% | F:68% R28:3% RAI:29% | 712.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R35:0% RAI:10% | F:68% R35:1% RAI:31% | 716.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R35:0% RAI:11% | F:68% R35:1% RAI:31% | 718.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:88% R28:1% RAI:11% | F:68% R28:3% RAI:29% | 710.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R35:0% RAI:11% | F:64% R35:1% RAI:36% | 715.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R35:0% RAI:11% | F:64% R35:0% RAI:36% | 717.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R36:0% RAI:11% | F:71% R36:0% RAI:29% | 715.3 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R35:0% RAI:11% | F:71% R35:0% RAI:28% | 712.2 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:90% R34:0% RAI:10% | F:60% R34:1% RAI:40% | 719.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R28:2% RAI:9% | F:75% R28:4% RAI:21% | 713.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R35:0% RAI:11% | F:67% R35:0% RAI:32% | 721.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:88% R35:1% RAI:10% | F:66% R35:4% RAI:30% | 712.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R36:1% RAI:11% | F:73% R36:2% RAI:25% | 720.5 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:88% R33:1% RAI:11% | F:73% R33:2% RAI:25% | 712.0 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:89% R35:0% RAI:11% | F:61% R35:0% RAI:38% | 719.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:91% R40:0% RAI:9% | F:81% R40:0% RAI:19% | 714.2 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:91% R40:0% RAI:9% | F:81% R40:0% RAI:18% | 718.4 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:91% R45:0% RAI:9% | F:73% R45:0% RAI:27% | 720.3 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:92% R37:0% RAI:8% | F:80% R37:0% RAI:20% | 717.7 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | iprayforgod | 129 | 23.3% | 21.4% | F:88% R29:1% RAI:11% | F:56% R29:4% RAI:40% | 897.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:88% R28:1% RAI:11% | F:56% R28:4% RAI:40% | 901.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R35:0% RAI:10% | F:56% R35:2% RAI:42% | 895.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R35:0% RAI:11% | F:57% R35:1% RAI:42% | 901.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:88% R28:1% RAI:11% | F:63% R28:4% RAI:33% | 911.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R35:0% RAI:11% | F:57% R35:1% RAI:42% | 902.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R35:0% RAI:11% | F:59% R35:0% RAI:41% | 897.5 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R36:0% RAI:11% | F:61% R36:1% RAI:38% | 903.8 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R35:0% RAI:11% | F:63% R35:1% RAI:36% | 897.6 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:90% R34:0% RAI:10% | F:49% R34:1% RAI:51% | 893.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R28:2% RAI:9% | F:71% R28:4% RAI:25% | 1329.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R35:0% RAI:11% | F:62% R35:0% RAI:38% | 909.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:88% R35:1% RAI:10% | F:61% R35:5% RAI:34% | 897.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R36:1% RAI:11% | F:64% R36:2% RAI:34% | 906.7 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:88% R33:1% RAI:11% | F:65% R33:3% RAI:33% | 912.5 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:89% R35:0% RAI:11% | F:49% R35:0% RAI:51% | 903.2 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:91% R40:0% RAI:9% | F:74% R40:0% RAI:25% | 902.3 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:91% R40:0% RAI:9% | F:76% R40:0% RAI:24% | 897.0 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:91% R45:0% RAI:9% | F:64% R45:0% RAI:36% | 891.6 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:92% R37:0% RAI:8% | F:73% R37:0% RAI:27% | 904.1 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | aafhs | 100 | 28.0% | 12.5% | F:88% R29:1% RAI:11% | F:74% R29:2% RAI:24% | 747.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:88% R28:1% RAI:11% | F:74% R28:2% RAI:24% | 749.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R35:0% RAI:10% | F:74% R35:1% RAI:25% | 753.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R35:0% RAI:11% | F:75% R35:1% RAI:25% | 1260.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:88% R28:1% RAI:11% | F:78% R28:2% RAI:20% | 751.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R35:0% RAI:11% | F:74% R35:0% RAI:25% | 753.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R35:0% RAI:11% | F:75% R35:0% RAI:25% | 749.8 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R36:0% RAI:11% | F:79% R36:0% RAI:21% | 752.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R35:0% RAI:11% | F:80% R35:0% RAI:20% | 753.4 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:90% R34:0% RAI:10% | F:69% R34:0% RAI:31% | 756.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R28:2% RAI:9% | F:82% R28:3% RAI:15% | 746.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R35:0% RAI:11% | F:77% R35:0% RAI:23% | 748.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:88% R35:1% RAI:10% | F:77% R35:3% RAI:21% | 756.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R36:1% RAI:11% | F:80% R36:1% RAI:19% | 750.6 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:88% R33:1% RAI:11% | F:80% R33:1% RAI:18% | 763.9 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:89% R35:0% RAI:11% | F:70% R35:0% RAI:30% | 759.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:91% R40:0% RAI:9% | F:86% R40:0% RAI:14% | 749.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:91% R40:0% RAI:9% | F:87% R40:0% RAI:13% | 757.0 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:91% R45:0% RAI:9% | F:79% R45:0% RAI:21% | 756.2 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:92% R37:0% RAI:8% | F:84% R37:0% RAI:16% | 753.7 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Oatta | 108 | 38.9% | 27.0% | F:88% R29:1% RAI:11% | F:43% R29:5% RAI:51% | 838.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:88% R28:1% RAI:11% | F:44% R28:5% RAI:51% | 842.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R35:0% RAI:10% | F:46% R35:2% RAI:52% | 844.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R35:0% RAI:11% | F:45% R35:2% RAI:53% | 855.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:88% R28:1% RAI:11% | F:53% R28:5% RAI:43% | 854.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R35:0% RAI:11% | F:45% R35:1% RAI:54% | 846.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R35:0% RAI:11% | F:48% R35:0% RAI:52% | 842.8 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R36:0% RAI:11% | F:55% R36:1% RAI:44% | 857.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R35:0% RAI:11% | F:58% R35:1% RAI:41% | 842.7 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:90% R34:0% RAI:10% | F:49% R34:1% RAI:51% | 846.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R28:2% RAI:9% | F:63% R28:6% RAI:32% | 843.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R35:0% RAI:11% | F:50% R35:0% RAI:49% | 844.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:88% R35:1% RAI:10% | F:51% R35:6% RAI:43% | 841.0 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R36:1% RAI:11% | F:58% R36:2% RAI:39% | 850.8 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:88% R33:1% RAI:11% | F:60% R33:3% RAI:37% | 848.7 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:89% R35:0% RAI:11% | F:46% R35:0% RAI:54% | 852.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:91% R40:0% RAI:9% | F:70% R40:0% RAI:29% | 857.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:91% R40:0% RAI:9% | F:73% R40:0% RAI:27% | 841.4 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:91% R45:0% RAI:9% | F:55% R45:0% RAI:45% | 849.6 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:92% R37:0% RAI:8% | F:65% R37:0% RAI:35% | 856.2 |

## 数据充足 (>300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | oleh2222 | 802 | 12.0% | 8.2% | F:88% R29:1% RAI:11% | F:85% R29:1% RAI:14% | 1341.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:88% R28:1% RAI:11% | F:86% R28:1% RAI:13% | 865.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R35:0% RAI:10% | F:87% R35:1% RAI:12% | 871.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R35:0% RAI:11% | F:89% R35:0% RAI:11% | 866.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:88% R28:1% RAI:11% | F:89% R28:1% RAI:10% | 863.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R35:0% RAI:11% | F:89% R35:0% RAI:11% | 863.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R35:0% RAI:11% | F:90% R35:0% RAI:10% | 871.5 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R36:0% RAI:11% | F:89% R36:0% RAI:10% | 872.7 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R35:0% RAI:11% | F:91% R35:0% RAI:9% | 865.9 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:90% R34:0% RAI:10% | F:84% R34:0% RAI:16% | 868.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R28:2% RAI:9% | F:91% R28:1% RAI:7% | 868.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R35:0% RAI:11% | F:90% R35:0% RAI:10% | 874.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:88% R35:1% RAI:10% | F:91% R35:1% RAI:8% | 1340.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R36:1% RAI:11% | F:90% R36:1% RAI:9% | 869.6 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:88% R33:1% RAI:11% | F:91% R33:1% RAI:8% | 876.9 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:89% R35:0% RAI:11% | F:85% R35:0% RAI:15% | 876.9 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:91% R40:0% RAI:9% | F:93% R40:0% RAI:7% | 873.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:91% R40:0% RAI:9% | F:94% R40:0% RAI:6% | 871.9 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:91% R45:0% RAI:9% | F:89% R45:0% RAI:11% | 884.5 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:92% R37:0% RAI:8% | F:92% R37:0% RAI:8% | 870.6 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Noris22 | 1124 | 24.6% | 16.1% | F:88% R29:1% RAI:11% | F:74% R29:2% RAI:23% | 797.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:88% R28:1% RAI:11% | F:77% R28:2% RAI:21% | 797.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R35:0% RAI:10% | F:78% R35:1% RAI:21% | 810.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R35:0% RAI:11% | F:81% R35:1% RAI:19% | 798.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:88% R28:1% RAI:11% | F:80% R28:2% RAI:18% | 799.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R35:0% RAI:11% | F:78% R35:0% RAI:22% | 808.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R35:0% RAI:11% | F:81% R35:0% RAI:19% | 806.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R36:0% RAI:11% | F:82% R36:0% RAI:17% | 804.2 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R35:0% RAI:11% | F:85% R35:0% RAI:15% | 805.0 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:90% R34:0% RAI:10% | F:77% R34:0% RAI:23% | 802.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R28:2% RAI:9% | F:84% R28:2% RAI:14% | 807.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R35:0% RAI:11% | F:80% R35:0% RAI:19% | 805.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:88% R35:1% RAI:10% | F:82% R35:2% RAI:16% | 808.0 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R36:1% RAI:11% | F:84% R36:1% RAI:16% | 824.5 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:88% R33:1% RAI:11% | F:85% R33:1% RAI:14% | 802.0 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:89% R35:0% RAI:11% | F:78% R35:0% RAI:22% | 810.1 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:91% R40:0% RAI:9% | F:88% R40:0% RAI:12% | 804.2 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:91% R40:0% RAI:9% | F:90% R40:0% RAI:10% | 808.1 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:91% R45:0% RAI:9% | F:85% R45:0% RAI:15% | 803.0 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:92% R37:0% RAI:8% | F:88% R37:0% RAI:12% | 804.4 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Dorororoo | 535 | 32.7% | 13.2% | F:88% R29:1% RAI:11% | F:74% R29:2% RAI:24% | 713.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:88% R28:1% RAI:11% | F:75% R28:2% RAI:23% | 702.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R35:0% RAI:10% | F:74% R35:1% RAI:25% | 710.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R35:0% RAI:11% | F:78% R35:1% RAI:22% | 707.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:88% R28:1% RAI:11% | F:80% R28:2% RAI:18% | 704.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R35:0% RAI:11% | F:76% R35:0% RAI:24% | 709.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R35:0% RAI:11% | F:79% R35:0% RAI:21% | 714.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R36:0% RAI:11% | F:81% R36:0% RAI:19% | 707.8 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R35:0% RAI:11% | F:83% R35:0% RAI:16% | 709.0 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:90% R34:0% RAI:10% | F:73% R34:0% RAI:27% | 708.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R28:2% RAI:9% | F:84% R28:2% RAI:14% | 708.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R35:0% RAI:11% | F:79% R35:0% RAI:21% | 713.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:88% R35:1% RAI:10% | F:81% R35:2% RAI:17% | 714.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R36:1% RAI:11% | F:82% R36:1% RAI:17% | 716.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:88% R33:1% RAI:11% | F:84% R33:1% RAI:15% | 713.1 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:89% R35:0% RAI:11% | F:74% R35:0% RAI:26% | 707.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:91% R40:0% RAI:9% | F:87% R40:0% RAI:13% | 711.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:91% R40:0% RAI:9% | F:89% R40:0% RAI:11% | 716.8 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:91% R45:0% RAI:9% | F:82% R45:0% RAI:18% | 710.3 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:92% R37:0% RAI:8% | F:86% R37:0% RAI:14% | 719.4 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Deteuler | 638 | 27.0% | 21.4% | F:88% R29:1% RAI:11% | F:62% R29:4% RAI:34% | 932.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:88% R28:1% RAI:11% | F:64% R28:3% RAI:33% | 938.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R35:0% RAI:10% | F:65% R35:1% RAI:33% | 941.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R35:0% RAI:11% | F:69% R35:1% RAI:30% | 936.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:88% R28:1% RAI:11% | F:66% R28:3% RAI:31% | 942.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R35:0% RAI:11% | F:62% R35:1% RAI:37% | 1381.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R35:0% RAI:11% | F:67% R35:0% RAI:33% | 948.3 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R36:0% RAI:11% | F:69% R36:0% RAI:31% | 940.8 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R35:0% RAI:11% | F:73% R35:0% RAI:27% | 934.9 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:90% R34:0% RAI:10% | F:56% R34:1% RAI:43% | 945.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R28:2% RAI:9% | F:73% R28:4% RAI:23% | 945.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R35:0% RAI:11% | F:66% R35:0% RAI:33% | 941.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:88% R35:1% RAI:10% | F:69% R35:4% RAI:28% | 947.6 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R36:1% RAI:11% | F:71% R36:2% RAI:27% | 939.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:88% R33:1% RAI:11% | F:74% R33:2% RAI:24% | 954.3 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:89% R35:0% RAI:11% | F:58% R35:0% RAI:42% | 946.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:91% R40:0% RAI:9% | F:79% R40:0% RAI:20% | 940.1 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:91% R40:0% RAI:9% | F:83% R40:0% RAI:17% | 1391.6 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:91% R45:0% RAI:9% | F:71% R45:0% RAI:29% | 949.3 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:92% R37:0% RAI:8% | F:78% R37:0% RAI:22% | 944.5 |

