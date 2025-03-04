import AuthService from '@/common/auth.service'

import {
  LOGOUT,
  CHECK_AUTH,
} from '@/store/actions.type'
import { SET_AUTH, PURGE_AUTH, SET_ERROR } from '@/store/mutations.type'

const defaults = {
  error: null,
  isAuthenticated: false,
  accessToken: null,
  refreshToken: null,
  user: {},
}

const state = Object.assign({}, defaults)

const getters = {
  currentUser(state: any) {
    return state.user
  },
  isAuthenticated (state: any) {
    return state.isAuthenticated
  },
}

const actions = {
  [LOGOUT](context: any) {
    context.commit(PURGE_AUTH)
    AuthService.logout()
  },
  [CHECK_AUTH](context: any) {
    return new Promise((resolve: any, reject: any) => {
      AuthService.getToken().then((jwt: any) => {
        context.commit(SET_AUTH, jwt)
        resolve('logged in')
      }).catch((err: any) => {
        console.log("CHECK_AUTH Error")
        console.log(err)
        context.commit(SET_ERROR, err)
        context.commit(PURGE_AUTH)
        reject('logging out')
      })
    })
  },
}

const mutations = {
  [SET_ERROR](state: any, error: any) {
    state.errors = error
  },
  [SET_AUTH](state: any, jwt: any) {
    state.isAuthenticated = true
    const startWithBackSlashRgx = /^\//i;
    state.user = {
        username: jwt.preferredUsername,
        roles: jwt.groups.filter((group: string) => group.startsWith('role:')).map((role: string) => role.slice('role:'.length)),
        groups: jwt.groups.filter((group: string) => !group.startsWith('role:')).map((groupname: string) => groupname.replace(startWithBackSlashRgx, '')),
        id: jwt.user
      }
    state.errors = {}
  },
  [PURGE_AUTH](state: any) {
    state.isAuthenticated = false
    state.user = {}
    state.errors = {}
  },
}
export default {
  state,
  actions,
  mutations,
  getters,
}
