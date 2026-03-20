# 3-Bet 场景测试报告

总耗时: 149731.2ms

## 数据不足 (<50手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R15:3% | F:97% R15:3% | 18.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R15:3% | F:97% R15:3% | 18.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R20:3% | F:97% R20:3% | 18.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R20:3% | F:97% R20:3% | 18.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R15:4% | F:97% R15:3% | 18.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R20:3% | F:97% R20:3% | 19.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R20:3% | F:97% R20:3% | 18.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R21:3% | F:96% R21:4% | 19.2 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R20:4% | F:96% R20:4% | 19.1 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R22:3% | F:96% R22:4% | 19.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R15:4% | F:97% R15:3% | 19.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R20:4% | F:97% R20:3% | 19.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:96% R20:4% | F:97% R20:3% | 19.0 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:95% R21:5% | F:95% R21:5% | 19.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:94% R21:6% | F:95% R21:5% | 19.8 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R22:3% | F:97% R22:3% | 19.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | xMichax | 4 | 0.0% | 0.0% | F:95% R21:5% | F:96% R21:4% | 19.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:94% R21:6% | F:96% R21:4% | 19.6 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R22:3% | F:98% R22:2% | 19.7 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | xMichax | 4 | 0.0% | 0.0% | F:97% R22:3% | F:98% R22:2% | 19.8 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | elvq | 12 | 16.7% | 16.7% | F:97% R15:3% | F:96% R15:4% | 419.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:97% R15:3% | F:95% R15:5% | 420.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R20:3% | F:96% R20:4% | 417.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R20:3% | F:96% R20:4% | 418.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:96% R15:4% | F:95% R15:5% | 418.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R20:3% | F:96% R20:4% | 418.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R20:3% | F:95% R20:5% | 422.7 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R21:3% | F:95% R21:5% | 421.5 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:96% R20:4% | F:95% R20:5% | 419.0 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R22:3% | F:95% R22:5% | 419.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | elvq | 12 | 16.7% | 16.7% | F:96% R15:4% | F:95% R15:5% | 419.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:96% R20:4% | F:96% R20:4% | 420.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:96% R20:4% | F:96% R20:4% | 417.5 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:95% R21:5% | F:94% R21:6% | 849.5 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:94% R21:6% | F:93% R21:7% | 430.3 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R22:3% | F:96% R22:4% | 419.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | elvq | 12 | 16.7% | 16.7% | F:95% R21:5% | F:95% R21:5% | 424.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:94% R21:6% | F:95% R21:5% | 422.7 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R22:3% | F:97% R22:3% | 425.4 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | elvq | 12 | 16.7% | 16.7% | F:97% R22:3% | F:98% R22:2% | 424.8 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R15:3% | F:97% R15:3% | 18.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R15:3% | F:97% R15:3% | 18.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R20:3% | F:97% R20:3% | 19.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R20:3% | F:97% R20:3% | 19.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R15:4% | F:97% R15:3% | 19.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R20:3% | F:97% R20:3% | 19.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R20:3% | F:97% R20:3% | 19.3 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R21:3% | F:96% R21:4% | 19.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R20:4% | F:96% R20:4% | 19.1 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R22:3% | F:96% R22:4% | 19.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R15:4% | F:97% R15:3% | 18.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R20:4% | F:97% R20:3% | 19.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:96% R20:4% | F:97% R20:3% | 19.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:95% R21:5% | F:95% R21:5% | 19.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:94% R21:6% | F:95% R21:5% | 19.6 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R22:3% | F:97% R22:3% | 19.9 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:95% R21:5% | F:96% R21:4% | 19.4 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:94% R21:6% | F:96% R21:4% | 20.0 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R22:3% | F:98% R22:2% | 19.5 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | afclockey49 | 6 | 83.3% | 0.0% | F:97% R22:3% | F:98% R22:2% | 19.9 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R15:3% | F:94% R15:6% | 413.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R15:3% | F:94% R15:6% | 411.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R20:3% | F:95% R20:5% | 414.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R20:3% | F:94% R20:6% | 412.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R15:4% | F:94% R15:6% | 411.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R20:3% | F:94% R20:6% | 415.5 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R20:3% | F:94% R20:6% | 414.0 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R21:3% | F:93% R21:7% | 410.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R20:4% | F:93% R20:7% | 413.7 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R22:3% | F:94% R22:6% | 410.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R15:4% | F:94% R15:6% | 410.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R20:4% | F:94% R20:6% | 416.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:96% R20:4% | F:94% R20:6% | 414.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:95% R21:5% | F:92% R21:8% | 412.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:94% R21:6% | F:91% R21:9% | 418.8 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R22:3% | F:95% R22:5% | 413.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Badforyou | 10 | 30.0% | 22.2% | F:95% R21:5% | F:94% R21:6% | 414.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:94% R21:6% | F:93% R21:7% | 418.3 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R22:3% | F:96% R22:4% | 413.2 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Badforyou | 10 | 30.0% | 22.2% | F:97% R22:3% | F:97% R22:3% | 412.8 |

## 数据中等 (50-300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R15:3% | F:96% R15:4% | 702.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R15:3% | F:96% R15:4% | 714.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R20:3% | F:96% R20:4% | 715.5 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R20:3% | F:96% R20:4% | 699.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R15:4% | F:95% R15:5% | 699.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R20:3% | F:96% R20:4% | 702.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R20:3% | F:95% R20:5% | 705.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R21:3% | F:95% R21:5% | 707.7 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R20:4% | F:95% R20:5% | 717.9 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R22:3% | F:96% R22:4% | 701.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R15:4% | F:95% R15:5% | 698.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R20:4% | F:96% R20:4% | 698.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:96% R20:4% | F:95% R20:5% | 703.8 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:95% R21:5% | F:94% R21:6% | 702.2 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:94% R21:6% | F:93% R21:7% | 704.9 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R22:3% | F:96% R22:4% | 710.3 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Turbem | 116 | 22.4% | 15.0% | F:95% R21:5% | F:96% R21:4% | 705.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:94% R21:6% | F:96% R21:4% | 702.9 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R22:3% | F:98% R22:2% | 710.4 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Turbem | 116 | 22.4% | 15.0% | F:97% R22:3% | F:98% R22:2% | 701.9 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R15:3% | F:95% R15:5% | 883.3 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R15:3% | F:95% R15:5% | 885.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R20:3% | F:95% R20:5% | 892.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R20:3% | F:95% R20:5% | 882.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R15:4% | F:95% R15:5% | 895.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R20:3% | F:95% R20:5% | 878.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R20:3% | F:95% R20:5% | 884.1 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R21:3% | F:94% R21:6% | 884.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R20:4% | F:93% R20:7% | 879.6 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R22:3% | F:94% R22:6% | 883.9 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R15:4% | F:94% R15:6% | 885.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R20:4% | F:95% R20:5% | 891.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:96% R20:4% | F:95% R20:5% | 883.4 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:95% R21:5% | F:92% R21:8% | 888.5 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:94% R21:6% | F:91% R21:9% | 886.8 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R22:3% | F:95% R22:5% | 1309.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:95% R21:5% | F:93% R21:7% | 887.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:94% R21:6% | F:93% R21:7% | 885.1 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R22:3% | F:96% R22:4% | 889.4 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | iprayforgod | 129 | 23.3% | 21.4% | F:97% R22:3% | F:97% R22:3% | 885.9 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R15:3% | F:97% R15:3% | 737.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R15:3% | F:97% R15:3% | 740.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R20:3% | F:97% R20:3% | 741.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R20:3% | F:97% R20:3% | 738.1 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R15:4% | F:97% R15:3% | 743.2 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R20:3% | F:97% R20:3% | 735.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R20:3% | F:97% R20:3% | 736.5 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R21:3% | F:97% R21:3% | 738.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R20:4% | F:96% R20:4% | 1152.2 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R22:3% | F:97% R22:3% | 736.6 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R15:4% | F:96% R15:4% | 732.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R20:4% | F:97% R20:3% | 742.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:96% R20:4% | F:97% R20:3% | 738.0 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:95% R21:5% | F:95% R21:5% | 735.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:94% R21:6% | F:95% R21:5% | 745.2 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R22:3% | F:97% R22:3% | 751.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | aafhs | 100 | 28.0% | 12.5% | F:95% R21:5% | F:96% R21:4% | 742.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:94% R21:6% | F:96% R21:4% | 746.5 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R22:3% | F:98% R22:2% | 739.6 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | aafhs | 100 | 28.0% | 12.5% | F:97% R22:3% | F:98% R22:2% | 751.3 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R15:3% | F:93% R15:7% | 833.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R15:3% | F:93% R15:7% | 1312.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R20:3% | F:93% R20:7% | 832.7 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R20:3% | F:93% R20:7% | 842.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R15:4% | F:93% R15:7% | 836.3 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R20:3% | F:93% R20:7% | 828.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R20:3% | F:93% R20:7% | 834.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R21:3% | F:93% R21:7% | 827.9 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R20:4% | F:92% R20:8% | 831.3 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R22:3% | F:93% R22:7% | 834.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R15:4% | F:92% R15:8% | 825.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R20:4% | F:93% R20:7% | 831.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:96% R20:4% | F:93% R20:7% | 833.0 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:95% R21:5% | F:90% R21:10% | 827.7 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:94% R21:6% | F:90% R21:10% | 832.9 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R22:3% | F:94% R22:6% | 835.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Oatta | 108 | 38.9% | 27.0% | F:95% R21:5% | F:93% R21:7% | 841.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:94% R21:6% | F:93% R21:7% | 839.2 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R22:3% | F:96% R22:4% | 837.6 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Oatta | 108 | 38.9% | 27.0% | F:97% R22:3% | F:97% R22:3% | 832.9 |

## 数据充足 (>300手)

### 紧被动 (低VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R15:3% | F:98% R15:2% | 856.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R15:3% | F:98% R15:2% | 856.1 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R20:3% | F:98% R20:2% | 850.2 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R20:3% | F:98% R20:2% | 850.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R15:4% | F:98% R15:2% | 855.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R20:3% | F:98% R20:2% | 1278.7 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R20:3% | F:98% R20:2% | 853.0 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R21:3% | F:98% R21:2% | 848.4 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R20:4% | F:98% R20:2% | 860.3 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R22:3% | F:98% R22:2% | 845.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R15:4% | F:98% R15:2% | 854.5 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R20:4% | F:98% R20:2% | 853.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:96% R20:4% | F:98% R20:2% | 855.3 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:95% R21:5% | F:97% R21:3% | 857.9 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:94% R21:6% | F:97% R21:3% | 862.0 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R22:3% | F:98% R22:2% | 858.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:95% R21:5% | F:98% R21:2% | 861.0 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:94% R21:6% | F:98% R21:2% | 857.3 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R22:3% | F:98% R22:2% | 856.1 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | oleh2222 | 802 | 12.0% | 8.2% | F:97% R22:3% | F:99% R22:1% | 851.2 |

### 紧激进 (低VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R15:3% | F:96% R15:4% | 794.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R15:3% | F:96% R15:4% | 785.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R20:3% | F:96% R20:4% | 784.9 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R20:3% | F:96% R20:4% | 793.9 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R15:4% | F:96% R15:4% | 789.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R20:3% | F:96% R20:4% | 795.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R20:3% | F:96% R20:4% | 794.2 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R21:3% | F:96% R21:4% | 792.1 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R20:4% | F:96% R20:4% | 796.7 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R22:3% | F:96% R22:4% | 791.3 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R15:4% | F:96% R15:4% | 797.4 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R20:4% | F:96% R20:4% | 793.7 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:96% R20:4% | F:96% R20:4% | 784.6 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:95% R21:5% | F:95% R21:5% | 794.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:94% R21:6% | F:95% R21:5% | 802.8 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R22:3% | F:97% R22:3% | 800.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:95% R21:5% | F:96% R21:4% | 798.5 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:94% R21:6% | F:96% R21:4% | 1223.9 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R22:3% | F:98% R22:2% | 796.7 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Noris22 | 1124 | 24.6% | 16.1% | F:97% R22:3% | F:98% R22:2% | 787.2 |

### 松被动 (高VPIP/低PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R15:3% | F:96% R15:4% | 694.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R15:3% | F:96% R15:4% | 697.8 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R20:3% | F:97% R20:3% | 698.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R20:3% | F:96% R20:4% | 697.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R15:4% | F:96% R15:4% | 699.0 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R20:3% | F:97% R20:3% | 692.4 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R20:3% | F:96% R20:4% | 704.7 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R21:3% | F:96% R21:4% | 697.8 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R20:4% | F:96% R20:4% | 696.5 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R22:3% | F:96% R22:4% | 695.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R15:4% | F:97% R15:3% | 1132.8 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R20:4% | F:97% R20:3% | 700.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:96% R20:4% | F:97% R20:3% | 695.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:95% R21:5% | F:96% R21:4% | 701.1 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:94% R21:6% | F:96% R21:4% | 697.0 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R22:3% | F:97% R22:3% | 697.6 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:95% R21:5% | F:97% R21:3% | 697.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:94% R21:6% | F:96% R21:4% | 700.8 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R22:3% | F:98% R22:2% | 697.7 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Dorororoo | 535 | 32.7% | 13.2% | F:97% R22:3% | F:98% R22:2% | 708.2 |

### 松激进 (高VPIP/高PFR)

| 位置组合 | 玩家 | 手数 | VPIP | PFR | 先验分布 | 后验分布 | 耗时(ms) |
|---------|------|------|------|-----|---------|---------|----------|
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.CO: 'CO'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R15:3% | F:95% R15:5% | 929.0 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R15:3% | F:95% R15:5% | 939.6 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R20:3% | F:96% R20:4% | 930.4 |
| (<Position.UTG: 'UTG'>, <Position.MP: 'MP'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R20:3% | F:95% R20:5% | 1339.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R15:4% | F:95% R15:5% | 934.6 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R20:3% | F:95% R20:5% | 929.8 |
| (<Position.UTG: 'UTG'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R20:3% | F:95% R20:5% | 928.6 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R21:3% | F:95% R21:5% | 927.1 |
| (<Position.UTG: 'UTG'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R20:4% | F:94% R20:6% | 928.4 |
| (<Position.UTG: 'UTG'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R22:3% | F:95% R22:5% | 920.0 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BTN: 'BTN'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R15:4% | F:95% R15:5% | 923.1 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R20:4% | F:95% R20:5% | 925.2 |
| (<Position.MP: 'MP'>, <Position.CO: 'CO'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:96% R20:4% | F:95% R20:5% | 921.6 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:95% R21:5% | F:93% R21:7% | 927.7 |
| (<Position.MP: 'MP'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:94% R21:6% | F:93% R21:7% | 935.2 |
| (<Position.MP: 'MP'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R22:3% | F:96% R22:4% | 927.7 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.SB: 'SB'>) | Deteuler | 638 | 27.0% | 21.4% | F:95% R21:5% | F:94% R21:6% | 926.8 |
| (<Position.CO: 'CO'>, <Position.BTN: 'BTN'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:94% R21:6% | F:94% R21:6% | 933.0 |
| (<Position.CO: 'CO'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R22:3% | F:96% R22:4% | 923.1 |
| (<Position.BTN: 'BTN'>, <Position.SB: 'SB'>, <Position.BB: 'BB'>) | Deteuler | 638 | 27.0% | 21.4% | F:97% R22:3% | F:97% R22:3% | 927.3 |

